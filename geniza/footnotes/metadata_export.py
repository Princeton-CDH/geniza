from geniza.common.metadata_export import Exporter
from geniza.footnotes.models import Footnote, Source


class SourceExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` that
    exports information relating to :class:`~geniza.footnotes.models.Source`.
    """

    model = Source
    csv_fields = [
        "source_type",
        "authors",
        "title",
        "journal_book",
        "volume",
        "issue",
        "year",
        "place_published",
        "publisher",
        "edition",
        "other_info",
        "page_range",
        "languages",
        "url",
        "notes",
        "citation",
        "slug",
        "num_footnotes",
    ]

    # queryset filter for content types included in this import
    content_type_filter = {
        "content_type__app_label__in": ["footnotes"],
        "content_type__model__in": [
            "source",
            "source_type",
            "creator",
            "footnote",
        ],
    }

    def get_queryset(self):
        qset = self.queryset or self.model.objects.all().metadata_prefetch()
        return qset.footnote_count()

    def get_export_data_dict(self, source):
        return {
            "source_type": source.source_type,
            # authors in order, lastname first
            "authors": [str(a.creator) for a in source.authorship_set.all()],
            "title": source.title,
            "journal_book": source.journal,
            "volume": source.volume,
            "issue": source.issue,
            "year": source.year,
            "place_published": source.place_published,
            "publisher": source.publisher,
            "edition": source.edition,
            "other_info": source.other_info,
            "page_range": source.page_range,
            "languages": {
                lang.name for lang in source.languages.all() if lang.code != "zxx"
            },
            "url": source.url,
            "notes": source.notes,
            "citation": str(source),
            "slug": source.slug,
            # count via annotated queryset
            "num_footnotes": source.footnote__count,
        }


class PublicSourceExporter(SourceExporter):
    """
    Like `geniza.corpus.metadata_export.PublicDocumentExporter` or `geniza.corpus.metadata_export.PublicFragmentExporter`,
    this class could filter sources in `get_queryset`, but the filter is not necessary.
    """

    pass


class AdminSourceExporter(SourceExporter):
    """Admin version of :class:`~geniza.footnotes.metadata_export.SourceExporter`;
    adds admin urls to the output."""

    csv_fields = SourceExporter.csv_fields + ["url_admin"]

    def get_export_data_dict(self, source):
        data = super().get_export_data_dict(source)
        # construct directly to avoid extra db calls
        data["url_admin"] = (
            f"{self.url_scheme}{self.site_domain}/admin/footnotes/source/{source.id}/change/"
        )
        return data


class FootnoteExporter(Exporter):
    """
    A subclass of :class:`geniza.common.metadata_export.Exporter` that
    exports public information relating to :class:`~geniza.footnotes.models.Footnote`.
    """

    model = Footnote
    csv_fields = [
        "document",  # ~ content object
        "document_id",
        "source",
        "source_slug",
        "location",
        "doc_relation",
        "emendations",
        "notes",
        "url",
        "content",
    ]

    # queryset filter for content types included in this import
    content_type_filter = {
        "content_type__app_label__in": ["corpus", "footnotes", "annotations"],
        "content_type__model__in": [
            "document",
            "source",
            "creator",
            "footnote",
            "annotation",
        ],
    }

    def get_queryset(self):
        return self.queryset or self.model.objects.all().metadata_prefetch()

    def get_export_data_dict(self, footnote):
        return {
            "document": footnote.content_object,
            "document_id": (
                footnote.content_object.pk
                if footnote.content_object is not None
                else None
            ),
            "source": footnote.source,
            "source_slug": footnote.source.slug,
            "location": footnote.location,
            "emendations": footnote.emendations,
            "doc_relation": footnote.get_doc_relation_list(),
            "notes": footnote.notes,
            "url": footnote.url,
            "content": footnote.content_text or "",
        }


class PublicFootnoteExporter(FootnoteExporter):
    """
    Like `geniza.corpus.metadata_export.PublicDocumentExporter` or `geniza.corpus.metadata_export.PublicFragmentExporter`,
    this class could filter footnotes in `get_queryset` that deal with public documents, but this filter is not necessary.
    """

    pass


class AdminFootnoteExporter(FootnoteExporter):
    """Admin version of :class:`~geniza.footnotes.metadata_export.FootnoteExporter`;
    adds admin urls to the output."""

    csv_fields = FootnoteExporter.csv_fields + ["url_admin"]

    def get_export_data_dict(self, footnote):
        data = super().get_export_data_dict(footnote)
        data["url_admin"] = (
            f"{self.url_scheme}{self.site_domain}/admin/footnotes/footnote/{footnote.id}/change/"
        )
        return data
