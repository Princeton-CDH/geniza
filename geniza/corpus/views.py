from ast import literal_eval
from random import randint

from dal import autocomplete
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.db.models.query import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.http.response import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.middleware.csrf import get_token as csrf_token
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.text import Truncator, slugify
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import DetailView, FormView, ListView
from django.views.generic.edit import FormMixin
from parasolr.django.views import SolrLastModifiedMixin
from piffle.presentation import IIIFPresentation
from tabular_export.admin import export_to_csv_response

from geniza.common.utils import absolutize_url
from geniza.corpus import iiif_utils
from geniza.corpus.forms import DocumentMergeForm, DocumentSearchForm
from geniza.corpus.models import Document, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.templatetags import corpus_extras
from geniza.footnotes.forms import SourceChoiceForm
from geniza.footnotes.models import Footnote, Source


class DocumentSearchView(ListView, FormMixin, SolrLastModifiedMixin):
    model = Document
    form_class = DocumentSearchForm
    context_object_name = "documents"
    template_name = "corpus/document_list.html"
    # Translators: title of document search page
    page_title = _("Search Documents")
    # Translators: description of document search page, for search engines
    page_description = _("Search and browse Geniza documents.")
    paginate_by = 50
    initial = {"sort": "random"}
    # NOTE: does not filter on status, since changing status could modify the page
    solr_lastmodified_filters = {"item_type_s": "document"}

    # map form sort to solr sort field
    solr_sort = {
        "relevance": "-score",
        "scholarship_desc": "-scholarship_count_i",
        "scholarship_asc": "scholarship_count_i",
        "input_date_desc": "-input_date_dt",
        "input_date_asc": "input_date_dt",
        "shelfmark": "shelfmark_s",
        "docdate_asc": "start_date_i",
        "docdate_desc": "-end_date_i",
    }

    def dispatch(self, request, *args, **kwargs):
        # special case: for random sort we only show the first page of results
        # if any other page is requested, redirect to first page
        if request.GET.get("sort") == "random" and request.GET.get("page", "") > "1":
            queryargs = request.GET.copy()
            del queryargs["page"]
            return HttpResponseRedirect(
                "?".join([reverse("corpus:document-search"), queryargs.urlencode()])
            )
        return super().dispatch(request, *args, **kwargs)

    def last_modified(self):
        """override last modified from solr mixin to not return a value when
        sorting by random"""
        if self.request.GET.get("sort") in [None, "random"]:
            return None
        return super().last_modified()

    def get_solr_sort(self, sort_option):
        """Return solr sort field for user-seleted sort option;
        generates random sort field using solr random dynamic field;
        otherwise uses solr sort field from :attr:`solr_sort`"""
        if sort_option == "random":
            # use solr's random dynamic field to sort randomly
            return "random_%s" % randint(1000, 9999)
        return self.solr_sort[sort_option]

    # NOTE: should cache this, shouldn't really change that frequently
    def get_range_stats(self):
        """Return the min and max for range fields based on Solr stats.

        :returns: Dictionary keyed on form field name with a tuple of
            (min, max) as integers. If stats are not returned from the field,
            the key is not added to a dictionary.
        :rtype: dict
        """
        stats = DocumentSolrQuerySet().stats("start_date_i", "end_date_i").get_stats()
        if stats.get("stats_fields"):
            # use minimum from start date and max from end date
            # - we're storing YYYYMMDD as 8-digit number for this we only want year
            # convert to str, take first 4 digits, then convert back to int
            min_val = stats["stats_fields"]["start_date_i"]["min"]
            max_val = stats["stats_fields"]["end_date_i"]["max"]

            # trim from the end to handle 3-digit years; includes .0 at end
            min_year = int(str(min_val)[:-6]) if min_val else None
            max_year = int(str(max_val)[:-6]) if max_val else None
            return {"docdate": (min_year, max_year)}

        return {}

    def get_form_kwargs(self):
        """get form arguments from request and configured defaults"""
        kwargs = super().get_form_kwargs()
        # use GET instead of default POST/PUT for form data
        form_data = self.request.GET.copy()

        # sort by chosen sort
        if "sort" in form_data and bool(form_data.get("sort")):
            form_data["sort"] = form_data.get("sort")
        # sort by relevance if query text exists and no sort chosen
        elif form_data.get("q", None):
            form_data["sort"] = "relevance"

        # Otherwise set all form values to default
        for key, val in self.initial.items():
            form_data.setdefault(key, val)

        # Handle empty string for sort
        if "sort" in form_data and not bool(form_data.get("sort")):
            form_data["sort"] = self.initial["sort"]

        kwargs["data"] = form_data
        # get min/max configuration for document date range field
        kwargs["range_minmax"] = self.get_range_stats()

        return kwargs

    def get_queryset(self):
        """Perform requested search and return solr queryset"""
        # limit to documents with published status (i.e., no suppressed documents);
        # get counts of facets, excluding type filter
        documents = (
            DocumentSolrQuerySet()
            .filter(status=Document.PUBLIC_LABEL)
            .facet(
                "has_image", "has_digital_edition", "has_translation", "has_discussion"
            )
            .facet_field("type", exclude="type", sort="value")
        )

        form = self.get_form()
        # return empty queryset if not valid
        if not form.is_valid():
            documents = documents.none()

        # when form is valid, check for search term and filter queryset
        else:
            search_opts = form.cleaned_data

            if search_opts["q"]:
                # NOTE: using requireFieldMatch so that field-specific search
                # terms will NOT be usind for highlighting text matches
                # (unless they are in the appropriate field)
                documents = (
                    documents.keyword_search(search_opts["q"])
                    .highlight(
                        "description",
                        snippets=3,
                        method="unified",
                        requireFieldMatch=True,
                    )
                    # return smaller chunk of highlighted text for transcriptions
                    # since the lines are often shorter, resulting in longer text
                    .highlight(
                        "transcription",
                        method="unified",
                        fragsize=150,  # try including more context
                        requireFieldMatch=True,
                    )
                    .also("score")
                )  # include relevance score in results

            # order by sort option
            documents = documents.order_by(self.get_solr_sort(search_opts["sort"]))

            # filter by type if specified
            if search_opts["doctype"]:
                typelist = literal_eval(search_opts["doctype"])
                quoted_typelist = ['"%s"' % doctype for doctype in typelist]
                documents = documents.filter(type__in=quoted_typelist, tag="type")

            # image filter
            if search_opts["has_image"] == True:
                documents = documents.filter(has_image=True)

            # scholarship filters
            if search_opts["has_transcription"] == True:
                documents = documents.filter(has_digital_edition=True)
            if search_opts["has_discussion"] == True:
                documents = documents.filter(has_discussion=True)
            if search_opts["has_translation"] == True:
                documents = documents.filter(has_translation=True)
            if search_opts["docdate"]:
                # date range filter; returns tuple of value or None for open-ended range
                start, end = search_opts["docdate"]
                documents = documents.filter(
                    document_date_dr="[%s TO %s]" % (start or "*", end or "*")
                )

        self.queryset = documents

        return documents

    def get_paginate_by(self, queryset):
        """Try to get pagination from GET request query,
        if there is none fallback to the original."""
        paginate_by = super().get_paginate_by(queryset)

        # NOTE: This may be reimplemented as a part of the form later
        req_params = self.request.GET.copy()
        if "per_page" in req_params:
            try:
                per_page = int(req_params["per_page"])
                if per_page < self.paginate_by:
                    paginate_by = per_page
            except:
                pass
        return paginate_by

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata, highlighting,
        and update form with facets"""
        context_data = super().get_context_data(**kwargs)

        paged_result = context_data["page_obj"].object_list
        highlights = paged_result.get_highlighting() if paged_result.count() else {}
        facet_dict = self.queryset.get_facets()
        # populate choices for facet filter fields on the form
        context_data["form"].set_choices_from_facets(facet_dict.facet_fields)
        context_data.update(
            {
                "highlighting": highlights,
                "page_description": self.page_description,
                "page_title": self.page_title,
                "page_type": "search",
                "page_includes_transcriptions": True,  # preload transcription font
                "highlighting": highlights,
            }
        )

        return context_data


class DocumentDetailBase(SolrLastModifiedMixin):
    """View mixin to handle lastmodified and redirects for documents with old PGPIDs.
    Overrides get request in the case of a 404, looking for any records
    with passed PGPID in old_pgpids, and if found, redirects to that document
    with current PGPID."""

    def get(self, request, *args, **kwargs):
        """extend GET to check for old pgpid and redirect on 404"""
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            # if not found, check for a match on a past PGPID
            doc = Document.objects.filter(
                old_pgpids__contains=[self.kwargs["pk"]]
            ).first()
            # if found, redirect to the correct url for this view
            if doc:
                self.kwargs["pk"] = doc.pk
                return HttpResponsePermanentRedirect(self.get_absolute_url())
            # otherwise, continue raising the 404
            raise

    def get_solr_lastmodified_filters(self):
        """Filter solr last modified query by pgpid"""
        return {"pgpid_i": self.kwargs["pk"], "item_type_s": "document"}


class DocumentDetailView(DocumentDetailBase, DetailView):
    """public display of a single :class:`~geniza.corpus.models.Document`"""

    model = Document
    context_object_name = "document"
    #: bound name of this view, for use in generating absolute url for redirect
    viewname = "corpus:document"

    def page_title(self):
        """page title, for metadata; uses document title"""
        return self.get_object().title

    def page_description(self):
        """page description, for metadata; uses truncated document description"""
        return Truncator(self.get_object().description).words(20)

    def get_queryset(self, *args, **kwargs):
        """Don't show document if it isn't public"""
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.filter(status=Document.PUBLIC)

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata"""
        context_data = super().get_context_data(**kwargs)
        context_data.update(
            {
                "page_title": self.page_title(),
                "page_description": self.page_description(),
                "page_type": "document",
                # preload transcription font when appropriate
                "page_includes_transcriptions": self.object.has_transcription(),
                # generate list of related documents that can be filtered by image url for links on excluded images
                "related_documents": [
                    {
                        "document": doc,
                        "images": [
                            str(image[0]) for image in doc.get("iiif_images", [])
                        ],
                    }
                    for doc in self.get_object().related_documents
                ]
                # skip solr query if none of the associated TextBlocks have side info
                if any([tb.side for tb in self.get_object().textblock_set.all()])
                else [],
            }
        )
        return context_data

    def get_absolute_url(self):
        """Get the permalink to this page."""
        return absolutize_url(reverse(self.viewname, args=[self.kwargs["pk"]]))


class DocumentScholarshipView(DocumentDetailView):
    """List of :class:`~geniza.footnotes.models.Footnote`
    references for a single :class:`~geniza.corpus.models.Document`"""

    template_name = "corpus/document_scholarship.html"
    viewname = "corpus:document-scholarship"

    def page_title(self):
        # Translators: title of document scholarship page
        return _("Scholarship on %(doc)s") % {"doc": self.get_object().title}

    def page_description(self):
        doc = self.get_object()
        count = doc.footnotes.count()
        # Translators: description of document scholarship page, for search engines
        return ngettext(
            "%(count)d scholarship record",
            "%(count)d scholarship records",
            count,
        ) % {
            "count": count,
        }

    def get_queryset(self, *args, **kwargs):
        """Prefetch footnotes, and don't show the page if there are none."""
        # prefetch footnotes since we'll render all of them in the template
        queryset = (
            super()
            .get_queryset(*args, **kwargs)
            .prefetch_related("footnotes")
            .distinct()  # prevent MultipleObjectsReturned if many footnotes
        )

        return queryset.filter(footnotes__isnull=False)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data.update(
            {
                "page_type": "scholarship",
                # transcription font not needed on this page
                "page_includes_transcriptions": False,
            }
        )
        return context_data


class RelatedDocumentView(DocumentDetailView):
    """List of :class:`~geniza.corpus.models.Document`
    objects that are related to specific :class:`~geniza.corpus.models.Document`
    (e.g., by occuring on the same shelfmark)."""

    template_name = "corpus/related_documents.html"
    viewname = "corpus:related-documents"

    def page_title(self):
        # Translators: title of related documents page
        return _("Related documents for %(doc)s") % {"doc": self.get_object().title}

    def page_description(self):
        doc = self.get_object()
        count = doc.related_documents.count()
        # Translators: description of related documents page, for search engines
        return ngettext(
            "%(count)d related document",
            "%(count)d related documents",
            count,
        ) % {
            "count": count,
        }

    def get_context_data(self, **kwargs):
        doc = self.get_object()
        # if there are no related documents, don't serve out this page
        if not doc.related_documents.count():
            raise Http404
        return super().get_context_data(**kwargs)


class DocumentTranscriptionText(DocumentDetailView):
    """Return transcription as plain text for download"""

    viewname = "corpus:document-transcription-text"

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        try:
            edition = document.digital_editions().get(
                pk=self.kwargs["transcription_pk"]
            )
            shelfmark = slugify(document.textblock_set.first().fragment.shelfmark)
            authors = [slugify(a.last_name) for a in edition.source.authors.all()]
            filename = "PGP%d_%s_%s.txt" % (document.id, shelfmark, "_".join(authors))

            return HttpResponse(
                edition.content_text,
                headers={
                    "Content-Type": "text/plain; charset=UTF-8",
                    # prompt download with filename including pgpid, shelfmark, & authors
                    "Content-Disposition": 'attachment; filename="%s"' % filename,
                },
            )
        except (Footnote.DoesNotExist, KeyError):
            # if there is no footnote, or no plain text content, return 404
            raise Http404


class DocumentManifestView(DocumentDetailView):
    """Generate a IIIF Presentation manifest for a document,
    incorporating available canvases and attaching transcription
    content via annotation."""

    viewname = "corpus:document-manifest"

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        # should 404 if no images or no transcription
        if not document.has_transcription() and not document.has_image():
            raise Http404

        iiif_urls = document.iiif_urls()
        local_manifest_id = self.get_absolute_url()
        first_canvas = None

        manifest = iiif_utils.new_iiif_manifest()
        manifest.id = local_manifest_id
        manifest.label = document.title
        # we probably want other metadata as well...
        manifest.metadata = [{"label": "PGP ID", "value": str(document.id)}]
        manifest.description = document.description

        canvases = []
        # keep track of unique attributions so we can include them all
        attributions = set()
        for url in iiif_urls:
            # NOTE: If this url fails, may raise IIIFException
            remote_manifest = IIIFPresentation.from_url(url)
            # CUDL attribution has some variation in tags;
            # would be nice to preserve tagged version,
            # for now, ignore tags so we can easily de-dupe
            try:
                attributions.add(strip_tags(remote_manifest.attribution))
            except AttributeError:
                # attribution is optional, so ignore if not present
                pass
            for canvas in remote_manifest.sequences[0].canvases:
                # do we want local canvas id, or rely on remote id?
                local_canvas = dict(canvas)
                if first_canvas is None:
                    first_canvas = local_canvas
                # TODO: can we build this from djiffy canvas?

                # adding provenance per recommendation from folks on IIIf Slack
                # to track original source of this canvas
                local_canvas["partOf"] = [
                    {
                        "@id": str(remote_manifest.id),
                        "@type": "sc:Manifest",
                        "label": {
                            "en": ["original source: %s" % remote_manifest.label]
                        },
                    }
                ]

                # NOTE: would be nice to attach the annotation list to every canvas,
                # so transcription will be available with any page,
                # but canvas id needs to match annotation target
                canvases.append(local_canvas)

        manifest.sequences = [{"@type": "sc:Sequence", "canvases": canvases}]
        # TODO: add a PGP logo here? combine logos?
        # NOTE: multiple logos do not seem to work with iiif presentation 2.0;
        # (or at least, do not display in Mirador)
        # in 3.0 we can use multiple provider blocks, but no viewer supports it yet

        manifest.attribution = corpus_extras.format_attribution(document.attribution())

        # if transcription is available, add an annotation list to first canvas
        if document.has_transcription():
            other_content = {
                "@context": "http://iiif.io/api/presentation/2/context.json",
                "@id": absolutize_url(
                    reverse("corpus:document-annotations", args=[document.pk]),
                    request=request,  # request is needed to avoid getting https:// urls in dev
                ),
                "@type": "sc:AnnotationList",
            }
            # if there are no images available, use an empty canvas
            if not first_canvas:
                first_canvas = iiif_utils.empty_iiif_canvas()
                canvases.append(first_canvas)

            # attach annotation list
            first_canvas["otherContent"] = other_content

        return JsonResponse(dict(manifest), encoder=iiif_utils.AttrDictEncoder)


class DocumentAnnotationListView(DocumentDetailView):
    """Generate a IIIF Annotation List for a document to make transcription
    content available for inclusion in local IIIF manifest."""

    viewname = "corpus:document-annotations"

    def get(self, request, *args, **kwargs):
        """handle GET request: construct and return JSON annotation list"""
        document = self.get_object()
        digital_editions = document.digital_editions()
        # if there is no transcription content, 404
        if not digital_editions:
            raise Http404

        # get absolute url for the current page to use as annotation list id
        annotation_list_id = self.get_absolute_url()
        # create outer annotation list structure
        annotation_list = iiif_utils.new_annotation_list()
        annotation_list.id = annotation_list_id
        # for now, annotate the first canvas
        # get a list of djiffy manifests
        manifests = [
            b.fragment.manifest
            for b in document.textblock_set.all()
            if b.fragment.iiif_url
        ]
        canvas = None
        if manifests and manifests[0]:
            canvas = manifests[0].canvases.first()
        # fallback to loading the remote manifest; (is this needed?)

        if not canvas:
            iiif_urls = document.iiif_urls()
            if iiif_urls:
                # NOTE: If this url fails, may raise IIIFException
                manifest = IIIFPresentation.from_url(iiif_urls[0])
                canvas = manifest.sequences[0].canvases[0]
            else:
                # if there are no images available, use an empty canvas
                canvas = iiif_utils.empty_iiif_canvas()

        resources = []
        digital_editions = document.digital_editions()
        # handle multiple transcriptions
        for i, transcription in enumerate(digital_editions, start=1):
            annotation = {
                # uri for this annotation; base on annotation list uri
                "@id": "%s#%d" % (annotation_list_id, i),
                "@type": "oa:Annotation",
                "motivation": "sc:painting",
                # transcribing should be a supported motivation (maybe 3.0?);
                # but mirador does not displayit
                # "motivation": "sc:transcribing",
                "resource": transcription.iiif_annotation_content(),
                # annotate the entire canvas for now
                "on": "%s#xywh=0,0,%d,%d" % (canvas.id, canvas.width, canvas.height),
            }
            resources.append(annotation)

        annotation_list["resources"] = resources

        return JsonResponse(dict(annotation_list), encoder=iiif_utils.AttrDictEncoder)


class DocumentMerge(PermissionRequiredMixin, FormView):
    permission_required = ("corpus.change_document", "corpus.delete_document")
    form_class = DocumentMergeForm
    template_name = "admin/corpus/document/merge.html"

    def get_success_url(self):
        return reverse("admin:corpus_document_change", args=[self.primary_document.id])

    def get_form_kwargs(self):
        form_kwargs = super(DocumentMerge, self).get_form_kwargs()
        form_kwargs["document_ids"] = self.document_ids
        return form_kwargs

    def get_initial(self):
        # Default to first document selected
        document_ids = self.request.GET.get("ids", None)
        if document_ids:
            self.document_ids = [int(pid) for pid in document_ids.split(",")]
            # by default, prefer the first record created
            return {"primary_document": sorted(self.document_ids)[0]}
        else:
            self.document_ids = []

    def form_valid(self, form):
        """Merge the selected documents into the primary document."""
        primary_doc = form.cleaned_data["primary_document"]
        self.primary_document = primary_doc

        # Include additional notes in rationale string if present
        if form.cleaned_data["rationale"] == "other":
            # Only use the additional notes if "other" is chosen
            rationale = form.cleaned_data["rationale_notes"]
        elif form.cleaned_data["rationale_notes"]:
            rationale = "%s (%s)" % (
                form.cleaned_data["rationale"],
                form.cleaned_data["rationale_notes"],
            )
        else:
            rationale = form.cleaned_data["rationale"]

        secondary_ids = [
            doc_id for doc_id in self.document_ids if doc_id != primary_doc.id
        ]
        secondary_docs = Document.objects.filter(id__in=secondary_ids)

        # Get document strings before they are merged
        primary_doc_str = f"PGPID {primary_doc.id}"
        secondary_doc_str = ", ".join([f"PGPID {doc.id}" for doc in secondary_docs])

        # Merge secondary documents into the selected primary document
        user = getattr(self.request, "user", None)
        primary_doc.merge_with(secondary_docs, rationale, user=user)

        # Display info about the merge to the user
        new_doc_link = reverse("admin:corpus_document_change", args=[primary_doc.id])
        messages.success(
            self.request,
            mark_safe(
                f"Successfully merged document(s) {secondary_doc_str} with {primary_doc_str}."
            ),
        )

        return super(DocumentMerge, self).form_valid(form)


class SourceAutocompleteView(PermissionRequiredMixin, autocomplete.Select2QuerySetView):
    permission_required = ("corpus.change_document",)

    def get_queryset(self):
        """sources filtered by entered query, or all sources, ordered by author last name"""
        q = self.request.GET.get("q", None)
        qs = Source.objects.all().order_by("authors__last_name")
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(authors__first_name__istartswith=q)
                | Q(authors__last_name__istartswith=q)
            ).distinct()
        return qs


class DocumentAddTranscriptionView(PermissionRequiredMixin, DetailView):
    permission_required = ("corpus.change_document",)
    template_name = "corpus/add_transcription_source.html"
    viewname = "corpus:document-add-transcription"
    model = Document

    def page_title(self):
        """Title of add transcription page"""
        return "Add a new transcription for %(doc)s" % {"doc": self.get_object().title}

    def post(self, request, *args, **kwargs):
        """Create footnote linking source to document, then redirect to edit transcription view"""
        return redirect(
            reverse(
                "corpus:document-transcribe",
                args=(self.get_object().id, int(request.POST["source"])),
            )
        )

    def get_context_data(self, **kwargs):
        """Pass form with autocomplete to context"""
        context_data = super().get_context_data(**kwargs)
        context_data.update(
            {
                "form": SourceChoiceForm,
                "page_title": self.page_title(),
                "page_type": "addsource",
            }
        )
        return context_data


class DocumentTranscribeView(PermissionRequiredMixin, DocumentDetailView):
    """View for the Transcription Editor page that uses annotorious-tahqiq"""

    permission_required = "corpus.change_document"

    template_name = "corpus/document_transcribe.html"
    viewname = "corpus:document-transcribe"

    def page_title(self):
        """Title of transcription editor page"""
        return "Edit transcription for %(doc)s" % {"doc": self.get_object().title}

    def get_context_data(self, **kwargs):
        """Pass annotation configuration and TinyMCE API key to page context"""
        context_data = super().get_context_data(**kwargs)

        source = None
        # source_pk will always be an integer here; otherwise, a different (or no) route
        # would have matched
        try:
            source = Source.objects.get(pk=self.kwargs["source_pk"])
        except Source.DoesNotExist:
            raise Http404

        context_data.update(
            {
                "annotation_config": {
                    # use local annotation server embedded in pgp application
                    "server_url": absolutize_url(reverse("annotations:list")),
                    # source uri for filtering, if we are editing an existing transcription
                    "source_uri": source.uri if source else "",
                    # use getattr to simplify test config; warn if not set?
                    "manifest_base_url": getattr(
                        settings, "ANNOTATION_MANIFEST_BASE_URL", ""
                    ),
                    "csrf_token": csrf_token(self.request),
                },
                "tiny_api_key": getattr(settings, "TINY_API_KEY", ""),
                "source_detail": mark_safe(
                    f"{source.formatted_display()} {source.notes}."
                )
                if source
                else "",
                "source_label": source.all_authors() if source else "",
                "page_type": "document annotating",
            }
        )
        return context_data


# --------------- Publish CSV to sync with old PGP site --------------------- #


def old_pgp_edition(editions):
    """output footnote and source information in a format similar to
    old pgp metadata editor/editions."""
    if editions:
        # label as translation if edition also supplies translation;
        # include url if any
        edition_list = [
            "%s%s%s"
            % (
                "and trans. " if Footnote.TRANSLATION in fn.doc_relation else "",
                fn.display().strip("."),
                " %s" % fn.url if fn.url else "",
            )
            for fn in editions
        ]
        # combine multiple editons as Ed. ...; also ed. ...
        return "".join(["Ed. ", "; also ed. ".join(edition_list), "."])

    return ""


def old_pgp_tabulate_data(queryset):
    """Takes a :class:`~geniza.corpus.models.Document` queryset and
    yields rows of data for serialization as csv in :meth:`pgp_metadata_for_old_site`"""
    # NOTE: This logic assumes that documents will always have a fragment
    for doc in queryset:
        primary_fragment = doc.textblock_set.first().fragment
        # combined shelfmark was included in the join column previously
        join_shelfmark = doc.shelfmark
        # library abbreviation; use collection abbreviation as fallback
        library = ""
        if primary_fragment.collection:
            library = (
                primary_fragment.collection.lib_abbrev
                or primary_fragment.collection.abbrev
            )

        yield [
            doc.id,  # pgpid
            library,  # library / collection
            primary_fragment.shelfmark,  # shelfmark
            primary_fragment.old_shelfmarks,  # shelfmark_alt
            doc.textblock_set.first().side,  # recto_verso
            doc.doctype,  # document type
            " ".join("#" + t.name for t in doc.tags.all()),  # tags
            join_shelfmark if " + " in join_shelfmark else "",  # join
            doc.description,  # description
            old_pgp_edition(doc.editions()),  # editor
            ";".join([str(i) for i in doc.old_pgpids]) if doc.old_pgpids else "",
        ]


def pgp_metadata_for_old_site(request):
    """Stream metadata in CSV format for index and display in the old PGP site."""

    # limit to documents with associated fragments, since the output
    # assumes a document has at least one frgment
    queryset = (
        Document.objects.filter(status=Document.PUBLIC, fragments__isnull=False)
        .order_by("id")
        .distinct()
        .select_related("doctype")
        .prefetch_related(
            "tags",
            "footnotes",
            # see corpus admin for notes on nested prefetch
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment", "fragment__collection"
                ),
            ),
        )
    )
    # return response
    return export_to_csv_response(
        "pgp_metadata.csv",
        [
            "pgpid",
            "library",
            "shelfmark",
            "shelfmark_alt",
            "recto_verso",
            "type",
            "tags",
            "joins",
            "description",
            "editor",
            "old_pgpids",
        ],
        old_pgp_tabulate_data(queryset),
    )


# --------------------------------------------------------------------------- #
