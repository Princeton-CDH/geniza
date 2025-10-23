import re
from ast import literal_eval
from copy import deepcopy
from random import randint

from dal import autocomplete
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.search import SearchVector
from django.core.exceptions import ValidationError
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
from taggit.models import Tag

from geniza.common.utils import absolutize_url
from geniza.corpus import iiif_utils
from geniza.corpus.forms import DocumentMergeForm, DocumentSearchForm, TagMergeForm
from geniza.corpus.ja import contains_arabic, contains_hebrew, ja_arabic_chars
from geniza.corpus.models import Document, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.templatetags import corpus_extras
from geniza.footnotes.forms import SourceChoiceForm
from geniza.footnotes.models import Footnote, Source


class SolrDateRangeMixin:
    """Mixin for solr-based views with start and end date fields to get
    the full range of dates across the solr queryset."""

    # NOTE: should cache this, shouldn't really change that frequently
    def get_range_stats(self, queryset_cls, field_name):
        """Return the min and max for range fields based on Solr stats.

        :returns: Dictionary keyed on form field name with a tuple of
            (min, max) as integers. If stats are not returned from the field,
            the key is not added to a dictionary.
        :rtype: dict
        """
        stats = queryset_cls().stats("start_dating_i", "end_dating_i").get_stats()
        if stats.get("stats_fields"):
            # use minimum from start date and max from end date
            # - we're storing YYYYMMDD as 8-digit number for this we only want year
            # convert to str, take first 4 digits, then convert back to int
            min_val = stats["stats_fields"]["start_dating_i"]["min"]
            max_val = stats["stats_fields"]["end_dating_i"]["max"]

            # trim from the end to handle 3-digit years; includes .0 at end
            min_year = int(str(min_val)[:-6]) if min_val else None
            max_year = int(str(max_val)[:-6]) if max_val else None
            return {field_name: (min_year, max_year)}

        return {}


class DocumentSearchView(
    ListView, FormMixin, SolrLastModifiedMixin, SolrDateRangeMixin
):
    model = Document
    form_class = DocumentSearchForm
    context_object_name = "documents"
    template_name = "corpus/document_list.html"
    # Translators: title of document search page
    page_title = _("Documents")
    # Translators: description of document search page, for search engines
    page_description = _("Search and browse Geniza documents.")
    paginate_by = 50
    initial = {"sort": "random", "mode": "general", "regex_field": "transcription"}
    # NOTE: does not filter on status, since changing status could modify the page
    solr_lastmodified_filters = {"item_type_s": "document"}
    applied_filter_labels = []

    # map form sort to solr sort field
    solr_sort = {
        "relevance": "-score",
        "scholarship_desc": "-scholarship_count_i",
        "scholarship_asc": "scholarship_count_i",
        "input_date_desc": "-input_date_dt",
        "input_date_asc": "input_date_dt",
        "shelfmark": "shelfmark_natsort",
        "docdate_asc": "start_date_i",
        "docdate_desc": "-end_date_i",
        "docdating_asc": "start_dating_i",
        "docdating_desc": "-end_dating_i",
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

    def get_solr_sort(self, sort_option, exclude_inferred=False):
        """Return solr sort field for user-seleted sort option;
        generates random sort field using solr random dynamic field;
        otherwise uses solr sort field from :attr:`solr_sort`"""
        if sort_option == "random":
            # use solr's random dynamic field to sort randomly
            return "random_%s" % randint(1000, 9999)
        elif "docdate" in sort_option and not exclude_inferred:
            # use inferred datings if exclude_inferred is not true
            sort_option = sort_option.replace("date", "dating")
        return self.solr_sort[sort_option]

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
        kwargs["range_minmax"] = self.get_range_stats(
            queryset_cls=DocumentSolrQuerySet, field_name="docdate"
        )

        return kwargs

    def get_applied_filter_labels(self, form, field, filters):
        """return a list of objects with field/value pairs, and translated labels,
        one for each applied filter"""
        labels = []
        for value in filters:
            # remove escape characters
            value = value.replace("\\", "")
            # get translated label using form helper method
            label = form.get_translated_label(field, value)
            # return object with original field and value, so we can unapply programmatically
            labels.append({"field": field, "value": value, "label": label})
        return labels

    def get_boolfield_label(self, form, fieldname):
        """Return a label dict for a boolean field (works differently than other fields)"""
        return {
            "field": fieldname,
            "value": "on",
            "label": form.fields[fieldname].label,
        }

    def get_queryset(self):
        """Perform requested search and return solr queryset"""
        # limit to documents with published status (i.e., no suppressed documents);
        # get counts of facets, excluding type filter
        documents = (
            DocumentSolrQuerySet()
            .filter(status=Document.PUBLIC_LABEL)
            .facet(
                "has_image",
                "has_digital_edition",
                "has_digital_translation",
                "has_discussion",
            )
            .facet_field(
                "translation_language", exclude="translation_language", sort="value"
            )
            .facet_field("type", exclude="type", sort="value")
        )
        self.applied_filter_labels = []

        form = self.get_form()
        # return empty queryset if not valid
        if not form.is_valid():
            documents = documents.none()

        # when form is valid, check for search term and filter queryset
        else:
            search_opts = form.cleaned_data

            if search_opts["q"] and search_opts["mode"] == "regex":
                regex_field = f"{search_opts['regex_field'] or 'transcription'}_regex"
                # use regex search if "mode" is "regex"
                documents = documents.regex_search(regex_field, search_opts["q"])

            elif search_opts["q"]:
                # NOTE: using requireFieldMatch so that field-specific search
                # terms will NOT be used for highlighting text matches
                # (unless they are in the appropriate field)
                documents = (
                    documents.keyword_search(search_opts["q"])
                    .highlight(
                        "description",
                        snippets=3,
                        method="unified",
                        requireFieldMatch=True,
                    )
                    .highlight(
                        "description_nostem",
                        snippets=3,
                        method="unified",
                        requireFieldMatch=True,
                    )
                    # return smaller chunk of highlighted text for transcriptions/translations
                    # since the lines are often shorter, resulting in longer text
                    .highlight(
                        "transcription",
                        method="unified",
                        fragsize=150,  # try including more context
                        requireFieldMatch=True,
                        # use newline as passage boundary
                        **{"bs.type": "SEPARATOR", "bs.separator": "\n"},
                    )
                    .highlight(
                        "translation",
                        method="unified",
                        fragsize=150,
                        requireFieldMatch=True,
                    )
                    .highlight(
                        "transcription_nostem",
                        method="unified",
                        fragsize=150,
                        requireFieldMatch=False,
                        **{"bs.type": "SEPARATOR", "bs.separator": "\n"},
                    )
                    # highlight old shelfmark so we can show match in results
                    .highlight("old_shelfmark", requireFieldMatch=True)
                    .highlight("old_shelfmark_t", requireFieldMatch=True)
                    .also("score")
                )  # include relevance score in results

            # order by sort option
            order_by = (
                self.get_solr_sort(
                    search_opts["sort"], search_opts.get("exclude_inferred", False)
                ),
            )
            # in all sorts except random and shelfmark, order
            # secondarily by shelfmark, in order to break ties
            if "random" not in order_by[0] and "shelfmark" not in order_by[0]:
                order_by += (self.solr_sort["shelfmark"],)
            documents = documents.order_by(*order_by)

            # filter by type if specified
            if search_opts["doctype"]:
                typelist = literal_eval(search_opts["doctype"])
                quoted_typelist = ['"%s"' % doctype for doctype in typelist]
                documents = documents.filter(type__in=quoted_typelist, tag="type")
                self.applied_filter_labels += self.get_applied_filter_labels(
                    form, "doctype", typelist
                )

            # filter by translation language if specified
            if search_opts["translation_language"]:
                lang = search_opts["translation_language"]
                documents = documents.filter(
                    translation_language=lang, tag="translation_language"
                )
                self.applied_filter_labels += self.get_applied_filter_labels(
                    form, "translation_language", [lang]
                )

            # image filter
            if search_opts["has_image"] == True:
                documents = documents.filter(has_image=True)
                self.applied_filter_labels.append(
                    self.get_boolfield_label(form, "has_image")
                )

            # scholarship filters
            if search_opts["has_transcription"] == True:
                documents = documents.filter(has_digital_edition=True)
                self.applied_filter_labels.append(
                    self.get_boolfield_label(form, "has_transcription")
                )
            if search_opts["has_discussion"] == True:
                documents = documents.filter(has_discussion=True)
                self.applied_filter_labels.append(
                    self.get_boolfield_label(form, "has_discussion")
                )
            if search_opts["has_translation"] == True:
                documents = documents.filter(has_digital_translation=True)
                self.applied_filter_labels.append(
                    self.get_boolfield_label(form, "has_translation")
                )
            if search_opts["no_transcription"] == True:
                documents = documents.filter(has_digital_edition=False)
                self.applied_filter_labels.append(
                    self.get_boolfield_label(form, "no_transcription")
                )
            if search_opts["docdate"]:
                # date range filter; returns tuple of value or None for open-ended range
                start, end = search_opts["docdate"]
                date_filter = "[%s TO %s]" % (start or "*", end or "*")
                date_field = (
                    "document_date_dr"
                    if search_opts.get("exclude_inferred", False)
                    else "document_dating_dr"
                )
                documents = documents.filter(**{date_field: date_filter})
                label = "%s–%s" % (start, end)
                if start and not end:
                    label = _("After %s") % start
                elif end and not start:
                    label = _("Before %s") % end
                self.applied_filter_labels += [
                    {
                        "field": "docdate",
                        "value": search_opts["docdate"],
                        "label": label,
                    }
                ]

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

    # base url for APD searches
    apd_base_url = "https://www.apd.gwi.uni-muenchen.de/apd/asearch.jsp?searchtable1=601&showdwords=true&searchwordstring1="

    def get_apd_link(self, query):
        """Generate a link to the Arabic Papyrology Database (APD) search page
        using the entered query, converting any Hebrew script to Arabic with Regex"""
        if not query or not (contains_arabic(query) or contains_hebrew(query)):
            # if no arabic OR hebrew in query, bail out
            return None
        # simplified version of ja_to_arabic that uses regex instead of solr OR
        for k, v in ja_arabic_chars.items():
            if type(v) == list:
                # list means there is more than one option, so join options with regex
                query = re.sub(k, f"[{''.join(v)}]", query)
            elif type(v) == str:
                # only one possible translation
                query = re.sub(k, v, query)
        query = query.strip()
        return f"{self.apd_base_url}{query}"

    def get_context_data(self, **kwargs):
        """extend context data to add page metadata, highlighting,
        and update form with facets"""
        context_data = super().get_context_data(**kwargs)

        paged_result = context_data["page_obj"].object_list
        highlights = paged_result.get_highlighting() if paged_result.count() else {}
        facet_dict = self.queryset.get_facets()
        # populate choices for facet filter fields on the form
        try:
            context_data["form"].set_choices_from_facets(facet_dict.facet_fields)
        except AttributeError:
            # in the event of a solr error (which causes an AttributeError on facet_dict),
            # reset queryset to none() so we can display facet fields
            self.queryset = self.queryset.none()
            facet_dict = self.queryset.get_facets()
            context_data["form"].set_choices_from_facets(facet_dict.facet_fields)
            if self.request.GET.get("mode") == "regex":
                context_data["form"].add_error(
                    "q", DocumentSearchForm.GENERIC_REGEX_ERROR
                )
        context_data.update(
            {
                "highlighting": highlights,
                "page_description": self.page_description,
                "page_title": self.page_title,
                "page_type": "search",
                "page_includes_transcriptions": True,  # preload transcription font
                "highlighting": highlights,
                "applied_filters": self.applied_filter_labels,
                "apd_link": self.get_apd_link(context_data["form"].data.get("q", None)),
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
        images = self.object.iiif_images(with_placeholders=True)

        # collect available panels
        available_panels = self.object.available_digital_content

        context_data.update(
            {
                "page_title": self.page_title(),
                "page_description": self.page_description(),
                "page_type": "document",
                # preload transcription font when appropriate
                "page_includes_transcriptions": self.object.has_transcription(),
                # generate list of related documents that can be filtered by image url for links on excluded images
                "related_documents": (
                    [
                        {
                            "document": doc,
                            "images": [
                                # TODO: can we use canvas uris here instead?
                                str(image[0])
                                for image in doc.get("iiif_images", [])
                            ],
                        }
                        for doc in self.object.related_documents
                    ]
                    # skip solr query if none of the associated TextBlocks have side info
                    if any([tb.side for tb in self.object.textblock_set.all()])
                    else []
                ),
                "images": images,
                # first image for twitter/opengraph meta tags
                "meta_image": list(images.values())[0]["image"] if images else None,
                # show all available panels by default
                "default_shown": available_panels,
                # disable any fully unavailable panels
                "disabled": [
                    panel
                    for panel in ["images", "translation", "transcription"]
                    if panel not in available_panels
                ],
                # related entities: sorted by type for grouping, and slug for alphabetization
                "related_people": self.object.persondocumentrelation_set.order_by(
                    "type__name", "person__slug"
                ),
                "related_places": self.object.documentplacerelation_set.order_by(
                    "type__name", "place__slug"
                ),
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

    viewname = "corpus-uris:document-manifest"

    def format_attribution(self, attribution):
        """format attribution for local manifests (deprecated)"""
        (attribution, additional_restrictions, extra_attrs_set) = attribution
        extra_attrs = "\n".join("<p>%s</p>" % attr for attr in extra_attrs_set)
        return '<div class="attribution"><p>%s</p><p>%s</p>%s</div>' % (
            attribution,
            additional_restrictions,
            extra_attrs,
        )

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

            # respect image order override if present
            ordered_canvases = []
            if document.image_overrides:
                # order returned images according to override: first, sort overrides by "order"
                sorted_overrides = sorted(
                    document.image_overrides.items(),
                    # get order if present; use ∞ as fallback to sort unordered to end of list
                    key=lambda item: item[1].get("order", float("inf")),
                )
                for canvas_id, _ in sorted_overrides:
                    matches = [
                        c
                        for c in remote_manifest.sequences[0].canvases
                        if c.id == canvas_id
                    ]
                    if matches:
                        ordered_canvases.append(matches[0])
            else:
                ordered_canvases = remote_manifest.sequences[0].canvases

            for canvas in ordered_canvases:
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

        manifest.attribution = self.format_attribution(document.attribution())

        # if transcription is available, add an annotation list to first canvas
        if document.has_transcription():
            other_content = {
                "@context": "http://iiif.io/api/presentation/2/context.json",
                "@id": absolutize_url(
                    reverse("corpus-uris:document-annotations", args=[document.pk]),
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

    viewname = "corpus-uris:document-annotations"

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

        try:
            primary_doc.merge_with(secondary_docs, rationale, user=user)
        except ValidationError as err:
            # in case the merge resulted in an error, display error to user
            messages.error(self.request, err.message)
            # redirect to this form page instead of one of the documents
            return HttpResponseRedirect(
                "%s?ids=%s"
                % (reverse("admin:document-merge"), self.request.GET.get("ids", "")),
            )

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
            qs = (
                qs.annotate(
                    # ArrayAgg to group together related values from related model instances
                    authors_last=ArrayAgg("authors__last_name", distinct=True),
                    authors_first=ArrayAgg("authors__first_name", distinct=True),
                    # PostgreSQL search vector to search across combined fields
                    search=SearchVector(
                        "title", "authors_last", "authors_first", "volume"
                    ),
                )
                .filter(search=q)
                .distinct()
            )
        return qs


class DocumentAddTranscriptionView(PermissionRequiredMixin, DetailView):
    permission_required = ("corpus.change_document",)
    template_name = "corpus/add_transcription_source.html"
    viewname = "corpus:document-add-transcription"
    model = Document
    doc_relation = "transcription"

    def page_title(self):
        """Title of add transcription/translation page"""
        return "Add a new %(doc_relation)s for %(doc)s" % {
            "doc_relation": self.doc_relation,
            "doc": self.get_object().title,
        }

    def post(self, request, *args, **kwargs):
        """Create footnote linking source to document, then redirect to edit transcription/translation view"""
        return redirect(
            reverse(
                (
                    "corpus:document-transcribe"
                    if self.doc_relation == "transcription"
                    else "corpus:document-translate"
                ),
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
                "doc_relation": self.doc_relation,
            }
        )
        return context_data


class DocumentTranscribeView(PermissionRequiredMixin, DocumentDetailView):
    """View for the Transcription/Translation Editor page that uses annotorious-tahqiq"""

    permission_required = "corpus.change_document"
    template_name = "corpus/document_transcribe.html"
    viewname = "corpus:document-transcribe"
    doc_relation = "transcription"

    def page_title(self):
        """Title of transcription/translation editor page"""
        return "Edit %(doc_relation)s for %(doc)s" % {
            "doc_relation": self.doc_relation,
            "doc": self.get_object().title,
        }

    def get_context_data(self, **kwargs):
        """Pass annotation configuration and TinyMCE API key to page context"""
        context_data = super().get_context_data(**kwargs)

        source = None
        # source_pk will always be an integer here; otherwise, a different (or no) route
        # would have matched
        try:
            source = Source.objects.get(pk=self.kwargs["source_pk"])
            source_label = (
                (source.all_authors() or str(source))
                if self.doc_relation == "transcription"
                else f"{source.all_authors()} {source.all_languages()}"
            )
        except Source.DoesNotExist:
            raise Http404

        # per each fragment without images, pass two placeholder canvases for use in editor
        for b in self.object.textblock_set.all():
            frag_images = b.fragment.iiif_images()
            if frag_images is None:
                canvas_base_uri = "%siiif/" % self.get_object().permalink
                for i in [1, 2]:
                    # create a placeholder canvas URI that contains textblock pk and canvas number
                    canvas_uri = f"{canvas_base_uri}textblock/{b.pk}/canvas/{i}/"
                    # assign the placeholder image and appropriate labels to this canvas
                    context_data["images"][canvas_uri] = deepcopy(
                        Document.PLACEHOLDER_CANVAS
                    )
                    context_data["images"][canvas_uri][
                        "shelfmark"
                    ] = b.fragment.shelfmark
                    context_data["images"][canvas_uri]["label"] = (
                        "recto" if i == 1 else "verso"
                    )
        # setup text direction for TinyMCE editor
        if self.doc_relation == "translation":
            # translation should use source language if possible, fallback ltr
            text_direction = (
                source.languages.first().direction
                if source and source.languages.exists()
                else "ltr"
            )
        else:
            # transcription always rtl
            text_direction = "rtl"

        # override show default/disabled logic from document detail view.
        # always show images and the panel we are editing, even if unavailable
        default_shown = ["images", self.doc_relation]
        # the third panel can still be disabled (e.g. transcription when editing translation)
        disabled = [p for p in context_data["disabled"] if p not in default_shown]

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
                    "tiny_api_key": getattr(settings, "TINY_API_KEY", ""),
                    "secondary_motivation": (
                        "transcribing"
                        if self.doc_relation == "transcription"
                        else "translating"
                    ),
                    "text_direction": text_direction,
                    "italic_enabled": self.doc_relation == "translation",
                    # line-by-line mode for eScriptorium sourced transcriptions
                    "line_mode": "model" in source.source_type.type,
                    # placeholder url for annotating a broken image
                    "placeholder_img": Document.PLACEHOLDER_CANVAS["image"]["info"],
                },
                # TODO: Add Footnote notes to the following display, if present
                "source_detail": (
                    mark_safe(source.formatted_display()) if source else ""
                ),
                "source_label": source_label if source_label else "",
                "authors_count": source.authors.count() if source else 0,
                "page_type": "document annotating",
                "disabled": disabled,
                "default_shown": default_shown,
            }
        )
        return context_data


class TagMerge(PermissionRequiredMixin, FormView):
    """Class-based view for merging tags, closely adapted from DocumentMerge."""

    permission_required = (
        "corpus.change_document",
        "taggit.change_tag",
        "taggit.delete_tag",
        "taggit.change_taggeditem",
        "taggit.add_taggeditem",
    )
    form_class = TagMergeForm
    template_name = "admin/corpus/tag/merge.html"

    def get_success_url(self):
        return reverse("admin:taggit_tag_change", args=[self.primary_tag.id])

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["tag_ids"] = self.tag_ids
        return form_kwargs

    def get_initial(self):
        # Default to first tag selected
        tag_ids = self.request.GET.get("ids", None)
        if tag_ids:
            self.tag_ids = [int(pid) for pid in tag_ids.split(",")]
            # by default, prefer the first record created
            return {"primary_tag": sorted(self.tag_ids)[0]}
        else:
            self.tag_ids = []

    @staticmethod
    def merge_tags(primary_tag, secondary_tags, user):
        """Merge secondary_tags into primary_tag: tag all documents tagged with any of the
        secondary_tags with the primary_tag, then delete all secondary_tags, and record
        the change with a LogEntry."""
        # add primary tag to all secondary tagged docs
        tagged_docs = Document.objects.filter(tags__in=secondary_tags)
        for doc in tagged_docs:
            doc.tags.add(primary_tag)
        # create a string for the logentry, then delete all secondary tags and log
        secondary_string = ", ".join([str(tag.name) for tag in secondary_tags])
        for tag in secondary_tags:
            tag.delete()
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=ContentType.objects.get_for_model(Tag).pk,
            object_id=primary_tag.pk,
            object_repr=str(primary_tag),
            change_message="merged with %s" % secondary_string,
            action_flag=CHANGE,
        )

    def form_valid(self, form):
        """Merge the selected tags into the primary tag."""
        primary_tag = form.cleaned_data["primary_tag"]
        self.primary_tag = primary_tag

        secondary_ids = [tag_id for tag_id in self.tag_ids if tag_id != primary_tag.id]
        secondary_tags = Tag.objects.filter(id__in=secondary_ids)

        # Get tag strings before they are merged
        primary_tag_str = primary_tag.name
        secondary_tag_str = ", ".join([tag.name for tag in secondary_tags])

        # Merge secondary tags into the selected primary tag
        user = getattr(self.request, "user", None)
        TagMerge.merge_tags(primary_tag, secondary_tags, user=user)

        # Display info about the merge to the user
        messages.success(
            self.request,
            mark_safe(
                f"Successfully merged tag(s) {secondary_tag_str} into {primary_tag_str}."
            ),
        )

        return super().form_valid(form)


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
                fn.display(old_pgp=True).strip("."),
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
