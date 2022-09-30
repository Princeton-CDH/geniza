import re

from parasolr.django import AliasedSolrQuerySet
from piffle.image import IIIFImageClient

from geniza.corpus.ja import arabic_or_ja


class DocumentSolrQuerySet(AliasedSolrQuerySet):
    """':class:`~parasolr.django.AliasedSolrQuerySet` for
    :class:`~geniza.corpus.models.Document`"""

    #: always filter to item records
    filter_qs = ["item_type_s:document"]

    #: map readable field names to actual solr fields
    field_aliases = {
        "id": "id",  # needed to match results with highlighting
        "type": "type_s",
        "status": "status_s",
        "shelfmark": "shelfmark_s",  # string version for display
        "document_date": "document_date_s",  # string version for display
        "collection": "collection_ss",
        "tags": "tags_ss_lower",
        "description": "description_txt_ens",  # use stemmed version for field search & highlight
        "notes": "notes_t",
        "needs_review": "needs_review_t",
        "pgpid": "pgpid_i",
        "old_pgpids": "old_pgpids_is",
        "input_year": "input_year_i",
        "input_date": "input_date_dt",
        "num_editions": "num_editions_i",
        "num_translations": "num_translations_i",
        "num_discussions": "num_discussions_i",
        "scholarship_count": "scholarship_count_i",
        "scholarship": "scholarship_t",
        "transcription": "transcription_t",
        "language_code": "language_code_ss",
        "iiif_images": "iiif_images_ss",
        "iiif_labels": "iiif_labels_ss",
        "has_image": "has_image_b",
        "has_digital_edition": "has_digital_edition_b",
        "has_translation": "has_translation_b",
        "has_discussion": "has_discussion_b",
    }

    # regex to convert field aliases used in search to actual solr fields
    # resulting regex will look something like: ((shelfmark|tags|decription|...):
    # adapted from https://stackoverflow.com/a/15448887
    # - start with a copy of default aliases
    # - define/override additional search aliases for site users
    search_aliases = field_aliases.copy()

    shelfmark_qf = "{!type=edismax qf=$shelfmark_qf}"

    search_aliases.update(
        {
            # when searching, singular makes more sense for tags & old pgpids
            "old_pgpid": field_aliases["old_pgpids"],
            "tag": field_aliases["tags"],
            # for shelfmark, use search field to search multiple formats
            "shelfmark": shelfmark_qf,
        }
    )

    re_solr_fields = re.compile(
        r"(%s):" % "|".join(key for key, val in search_aliases.items() if key != val),
        flags=re.DOTALL,
    )

    def _search_term_cleanup(self, search_term):
        # adjust user search string before sending to solr

        # ignore " + " in search strings, so users can search on shelfmark joins
        search_term = search_term.replace(" + ", " ")

        # convert any field aliases used in search terms to actual solr fields
        # (i.e. "pgpid:950 shelfmark:ena" -> "pgpid_i:950 shelfmark_t:ena")
        if ":" in search_term:
            # if any of the field aliases occur with a colon, replace with actual solr field
            search_term = self.re_solr_fields.sub(
                lambda x: "%s:" % self.search_aliases[x.group(1)], search_term
            )
            # special case: shelfmark edismax query should NOT have colon
            # like other fields
            search_term = search_term.replace(
                "%s:" % self.shelfmark_qf, self.shelfmark_qf
            )

        return arabic_or_ja(search_term)

    # (adapted from mep)
    # edismax alias for searching on admin document pseudo-field
    admin_doc_qf = "{!edismax qf=$admin_doc_qf pf=$admin_doc_pf v=$doc_query}"

    def admin_search(self, search_term):
        # remove " + " from search string to allow searching on shelfmark joins
        return self.search(self.admin_doc_qf).raw_query_parameters(
            doc_query=self._search_term_cleanup(search_term)
        )

    keyword_search_qf = "{!type=edismax qf=$keyword_qf pf=$keyword_pf v=$keyword_query}"

    def keyword_search(self, search_term):
        return self.search(self.keyword_search_qf).raw_query_parameters(
            keyword_query=self._search_term_cleanup(search_term)
        )

    def related_to(self, document):
        "Return documents related to the given document (i.e. shares any shelfmarks)"

        # NOTE: using a string query filter because parasolr queryset
        # # currently doesn't provide any kind of not/exclude filter
        return (
            self.filter(status=document.PUBLIC_LABEL)
            .filter("NOT pgpid_i:%d" % document.id)
            .filter(
                fragment_shelfmark_ss__in=[
                    '"%s"' % f.shelfmark for f in document.fragments.all()
                ]
            )
        )

    def get_result_document(self, doc):
        # default implementation converts from attrdict to dict
        doc = super().get_result_document(doc)
        # convert indexed iiif image paths to IIIFImageClient objects
        images = doc.get("iiif_images", [])
        doc["iiif_images"] = [IIIFImageClient(*img.rsplit("/", 1)) for img in images]
        # zip images and associated labels into (img, label) tuples in result doc
        labels = doc.get("iiif_labels", [])
        doc["iiif_images"] = list(zip(doc["iiif_images"], labels))
        return doc
