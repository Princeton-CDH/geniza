from django.db.models.query import Prefetch

from geniza.common.metadata_export import Exporter
from geniza.corpus.models import Document, Fragment
from geniza.footnotes.models import Footnote


class DocumentExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` that
    exports information relating to :class:`~geniza.corpus.models.Document`.
    Extends :meth:`get_queryset` and :meth:`get_export_data_dict`.
    """

    model = Document
    csv_fields = [
        "pgpid",
        "url",
        "iiif_urls",
        "fragment_urls",
        "shelfmark",
        "multifragment",
        "side",
        "region",
        "type",
        "tags",
        "description",
        "scholarship_records",
        "shelfmarks_historic",
        "languages_primary",
        "languages_secondary",
        "language_note",
        "doc_date_original",
        "doc_date_calendar",
        "doc_date_standard",
        "inferred_date_display",
        "inferred_date_standard",
        "inferred_date_rationale",
        "inferred_date_notes",
        "initial_entry",
        "last_modified",
        "input_by",
        "library",
        "collection",
        "has_transcription",
        "has_translation",
    ]

    # queryset filter for content types included in this import
    content_type_filter = {
        "content_type__app_label__in": ["corpus", "footnotes"],
        "content_type__model__in": [
            "document",
            "fragment",
            "collection",
            "languagescript",
            "footnote",
            "source",
            "creator",
            "languages",
        ],
    }

    def get_queryset(self):
        """
        Applies some prefetching to the base Exporter's get_queryset functionality.

        :return: Custom-given query set or query set of all documents
        :rtype: QuerySet
        """
        qset = self.queryset or self.model.objects.all()
        # clear existing prefetches and then add the ones we need,
        # since admin queryset footnote prefetching conflicts
        qset = (
            qset.prefetch_related(None)
            .metadata_prefetch()
            .prefetch_related(
                "secondary_languages",
                "log_entries",
                "log_entries__user",
                "dating_set",
                Prefetch(
                    "footnotes",
                    queryset=Footnote.objects.select_related(
                        "source",
                        "source__source_type",
                    ).prefetch_related(
                        "source__authorship_set__creator",
                        "source__languages",
                        "source__authors",
                    ),
                ),
            )
            .order_by("id")
        )
        return qset

    def get_export_data_dict(self, doc):
        """
        Get back data about a document in dictionary format.

        :param doc: A given Document object
        :type doc: Document

        :return: Dictionary of data about the document
        :rtype: dict
        """
        all_textblocks = doc.textblock_set.all()
        # if len(all_textblocks)>1:
        #    print(f'Doc text blocks: {doc.id} -> {[x.id for x in all_textblocks]}')
        all_fragments = [tb.fragment for tb in all_textblocks]
        all_log_entries = doc.log_entries.all()
        input_users = {
            log_entry.user
            for log_entry in all_log_entries
            if log_entry.user.username != self.script_user
        }
        iiif_urls = [fr.iiif_url for fr in all_fragments]
        view_urls = [fr.url for fr in all_fragments]
        multifrag = [tb.multifragment for tb in all_textblocks]
        side = [tb.side for tb in all_textblocks]
        region = [tb.region for tb in all_textblocks]
        old_shelfmarks = [fragment.old_shelfmarks for fragment in all_fragments]
        libraries = [
            fragment.collection.lib_abbrev or fragment.collection.library
            for fragment in all_fragments
            if fragment.collection
        ]
        collections = [
            str(fragment.collection)
            for fragment in all_fragments
            if fragment.collection
        ]
        datings = doc.dating_set.all()

        outd = {}
        outd["pgpid"] = doc.id

        # to make the download as efficient as possible, don't use
        # absolutize_url, reverse, or get_absolute_url methods
        outd[
            "url"
        ] = f"{self.url_scheme}{self.site_domain}/documents/{doc.id}/"  # public site url

        sep_within_cells = self.sep_within_cells

        outd["iiif_urls"] = iiif_urls
        outd["fragment_urls"] = view_urls
        outd["shelfmark"] = doc.shelfmark
        outd["multifragment"] = [s for s in multifrag if s]
        outd["side"] = [s for s in side if s]
        outd["region"] = [r for r in region if r]
        outd["type"] = doc.doctype
        outd["tags"] = doc.all_tags()
        outd["description"] = doc.description
        # include short display version of scholarship records;
        # need to use set since some sources have duplicate footnotes
        # in order to keep track of multiple links / PDFs
        outd["scholarship_records"] = {fn.display() for fn in doc.footnotes.all()}
        outd["shelfmarks_historic"] = [os for os in old_shelfmarks if os]
        outd["languages_primary"] = doc.all_languages()
        outd["languages_secondary"] = doc.all_secondary_languages()
        outd["language_note"] = doc.language_note
        outd["doc_date_original"] = doc.doc_date_original
        outd["doc_date_calendar"] = doc.get_doc_date_calendar_display()
        outd["doc_date_standard"] = doc.doc_date_standard
        outd["inferred_date_display"] = [
            dating.display_date for dating in datings if dating.display_date
        ]
        outd["inferred_date_standard"] = [
            dating.standard_date for dating in datings if dating.standard_date
        ]
        outd["inferred_date_rationale"] = [
            dating.get_rationale_display() for dating in datings if dating.notes
        ]
        outd["inferred_date_notes"] = [
            dating.notes for dating in datings if dating.notes
        ]

        # default sort is most recent first, so initial input is last
        # convert to list so we can do negative indexing, instead of calling last()
        # which incurs a database call
        outd["initial_entry"] = (
            list(all_log_entries)[-1].action_time if all_log_entries else ""
        )

        outd["last_modified"] = doc.last_modified

        outd["input_by"] = {
            user.get_full_name() or user.username for user in input_users
        }
        outd["library"] = libraries
        outd["collection"] = collections

        # has transcription and translation?
        outd["has_transcription"] = doc.has_transcription()
        outd["has_translation"] = doc.has_translation()

        return outd


class AdminDocumentExporter(DocumentExporter):
    csv_fields = DocumentExporter.csv_fields + [
        "notes",
        "needs_review",
        "status",
        "url_admin",
    ]

    def get_export_data_dict(self, doc):
        """
        Adding certain fields to DocumentExporter.get_export_data_dict that are admin-only.
        """

        outd = super().get_export_data_dict(doc)
        outd["notes"] = doc.notes
        outd["needs_review"] = doc.needs_review
        outd["status"] = doc.get_status_display()
        outd[
            "url_admin"
        ] = f"{self.url_scheme}{self.site_domain}/admin/corpus/document/{doc.id}/change/"

        return outd


class PublicDocumentExporter(DocumentExporter):
    """
    Public version of the document exporter. It can e.g. modify the get_queryset to ensure it deals with public documents.
    """

    def get_queryset(self):
        return super().get_queryset().filter(status=Document.PUBLIC)


class FragmentExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` that
    exports information relating to :class:`~geniza.corpus.models.Fragment`.
    """

    model = Fragment
    csv_fields = [
        "shelfmark",
        "pgpids",
        "old_shelfmarks",
        "collection",
        "library",
        "library_abbrev",
        "collection_name",
        "collection_abbrev",
        "url",
        "iiif_url",
        "is_multifragment",
        "created",
        "last_modified",
    ]

    # queryset filter for content types included in this import
    content_type_filter = {
        "content_type__app_label__in": ["corpus"],
        "content_type__model__in": ["document", "fragment", "collection"],
    }

    def get_queryset(self):
        """
        Applies some prefetching to the base Exporter's get_queryset functionality.

        :return: Custom-given query set or query set of all documents
        :rtype: QuerySet
        """
        return (
            super()
            .get_queryset()
            .select_related("collection")
            .prefetch_related("documents")
        )

    def get_export_data_dict(self, fragment):
        data = {
            "shelfmark": fragment.shelfmark,
            "pgpids": [doc.pk for doc in fragment.documents.all()],
            "old_shelfmarks": fragment.old_shelfmarks,
            "url": fragment.url,
            "iiif_url": fragment.iiif_url,
            "is_multifragment": fragment.is_multifragment,
            "created": fragment.created,
            "last_modified": fragment.last_modified,
        }
        # it's possible (although unlikely) for collection to be unset
        if fragment.collection:
            # NOTE: this results in a lot of redundant info;
            # maybe collection shortname is enough for fragment csv?
            data.update(
                {
                    "collection": fragment.collection,
                    "library": fragment.collection.library,
                    "library_abbrev": fragment.collection.lib_abbrev,
                    "collection_name": fragment.collection.name,
                    "collection_abbrev": fragment.collection.abbrev,
                }
            )
        return data


class PublicFragmentExporter(FragmentExporter):
    """
    Public version of the fragment exporter; limits fragments
    to those associated with public documents. Unassociated fragments
    or fragments only linked to suppressed documents are not included.
    """

    def get_queryset(self):
        # must use distinct() as filtering on documents__status produces
        # duplicate rows for fragments on multiple documents
        return (
            super().get_queryset().filter(documents__status=Document.PUBLIC).distinct()
        )


class AdminFragmentExporter(FragmentExporter):
    "Admin fragment export variant; adds notes, review, and admin url fields."

    csv_fields = FragmentExporter.csv_fields + ["notes", "needs_review", "url_admin"]

    def get_export_data_dict(self, fragment):
        data = super().get_export_data_dict(fragment)
        data["notes"] = fragment.notes
        data["needs_review"] = fragment.needs_review
        data[
            "url_admin"
        ] = f"{self.url_scheme}{self.site_domain}/admin/corpus/fragment/{fragment.id}/change/"
        return data
