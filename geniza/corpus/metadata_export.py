from geniza.common.metadata_export import Exporter
from geniza.corpus.models import Document


class DocumentExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` that
    exports information relating to :class:`~geniza.corpus.models.Documents`.
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
        "shelfmarks_historic",
        "languages_primary",
        "languages_secondary",
        "language_note",
        "doc_date_original",
        "doc_date_calendar",
        "doc_date_standard",
        "notes",
        "needs_review",
        "url_admin",
        "initial_entry",
        "last_modified",
        "input_by",
        "status",
        "library",
        "collection",
        "has_transcription",
        "has_translation",
    ]

    def get_queryset(self):
        """
        Applies some prefetching to the base Exporter's get_queryset functionality.

        :return: Custom-given query set or query set of all documents
        :rtype: QuerySet
        """
        qset = self.queryset or self.model.objects.all().metadata_prefetch()
        qset = qset.prefetch_related(
            "secondary_languages", "log_entries", "log_entries__user"
        ).order_by("id")
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
        all_fragments = [tb.fragment for tb in all_textblocks]
        all_log_entries = doc.log_entries.all()
        input_users = set(
            [
                log_entry.user
                for log_entry in all_log_entries
                if log_entry.user.username != self.script_user
            ]
        )
        iiif_urls = [fr.iiif_url for fr in all_fragments]
        view_urls = [fr.url for fr in all_fragments]
        multifrag = [tb.multifragment for tb in all_textblocks]
        side = [tb.side for tb in all_textblocks]
        region = [tb.region for tb in all_textblocks]
        old_shelfmarks = [fragment.old_shelfmarks for fragment in all_fragments]
        libraries = set(
            [
                fragment.collection.lib_abbrev or fragment.collection.library
                if fragment.collection
                else ""
                for fragment in all_fragments
            ]
        ) - {
            ""
        }  # exclude empty string for any fragments with no library
        collections = set(
            [
                fragment.collection.abbrev or fragment.collection.name
                if fragment.collection
                else ""
                for fragment in all_fragments
            ]
        ) - {
            ""
        }  # exclude empty string for any with no collection

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
        outd["shelfmarks_historic"] = [os for os in old_shelfmarks if os]
        outd["languages_primary"] = doc.all_languages()
        outd["languages_secondary"] = doc.all_secondary_languages()
        outd["language_note"] = doc.language_note
        outd["doc_date_original"] = doc.doc_date_original
        outd["doc_date_calendar"] = doc.get_doc_date_calendar_display()
        outd["doc_date_standard"] = doc.doc_date_standard

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
    Public version of the document exporter. It does not need to subset the list of CSV fields;
    the csv.DictWriter will use all fields in DocumentExporter.csv_fields that are also in the
    output dictionary given to the writer.
    """

    def get_queryset(self):
        return super().get_queryset().filter(status=Document.PUBLIC)
