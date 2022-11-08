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
        "num_footnotes",
        "admin_url",
    ]

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
            "languages": [lang.name for lang in source.languages.all()],
            "url": source.url,
            "notes": source.notes,
            # count via annotated queryset
            "num_footnotes": source.footnote__count,
            # construct directly to avoid extra db calls
            "admin_url": f"{self.url_scheme}{self.site_domain}/admin/footnotes/source/{source.id}/change/",
        }
