import re

from parasolr.django import AliasedSolrQuerySet
from piffle.image import IIIFImageClient


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
        "shelfmark": "shelfmark_t",
        "collection": "collection_ss",
        "tags": "tags_ss_lower",
        "description": "description_t",
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
    }

    # regex to convert field aliases used in search to actual solr fields
    # resulting regex will look something like: ((shelfmark|tags|decription|...):
    # adapted from https://stackoverflow.com/a/15448887
    # - define additional search aliases for site users
    search_aliases = {
        # when searching, singular makes more sense for tags & old pgpids
        "old_pgpid": field_aliases["old_pgpids"],
        "tag": field_aliases["tags"],
    }
    # - update to include all default aliases
    search_aliases.update(field_aliases)

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

        return search_term

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
