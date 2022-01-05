import re

from parasolr.django import AliasedSolrQuerySet


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
        "tags": "tags_ss",
        "description": "description_t",
        "notes": "notes_t",
        "needs_review": "needs_review_t",
        "pgpid": "pgpid_i",
        "old_pgpids": "old_pgpid_is",
        "input_year": "input_year_i",
        "input_date": "input_date_dt",
        "num_editions": "num_editions_i",
        "num_translations": "num_translations_i",
        "num_discussions": "num_discussions_i",
        "scholarship_count": "scholarship_count_i",
        "scholarship": "scholarship_t",
        "transcription": "transcription_t",
        "language_code": "language_code_ss",
    }

    # (adapted from mep)
    # edismax alias for searching on admin document pseudo-field
    admin_doc_qf = "{!edismax qf=$admin_doc_qf pf=$admin_doc_pf v=$doc_query}"

    def admin_search(self, search_term):
        # remove " + " from search string to allow searching on shelfmark joins
        return self.search(self.admin_doc_qf).raw_query_parameters(
            doc_query=search_term.replace(" + ", " ")
        )

    keyword_search_qf = "{!type=edismax qf=$keyword_qf pf=$keyword_pf v=$keyword_query}"

    # regex to convert field aliases to actual solr fields
    # adapted from https://stackoverflow.com/a/15448887
    re_solr_fields = re.compile(
        r"(%s):" % "|".join(key for key, val in field_aliases.items() if key != val),
        flags=re.DOTALL,
    )

    def keyword_search(self, search_term):
        # ignore " + " in search strings here too, for search on shelfmark joins

        # to support advanced search, convert field aliases to actual solr fields
        if ":" in search_term:
            # if any of the field aliases occur with a colon, replace with actual solr field
            search_term = self.re_solr_fields.sub(
                lambda x: "%s:" % self.field_aliases[x.group(1)], search_term
            )

        return self.search(self.keyword_search_qf).raw_query_parameters(
            keyword_query=search_term.replace(" + ", " ")
        )
