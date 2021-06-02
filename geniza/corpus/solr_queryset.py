from parasolr.django import AliasedSolrQuerySet


class DocumentSolrQuerySet(AliasedSolrQuerySet):
    """':class:`~parasolr.django.AliasedSolrQuerySet` for
    :class:`~geniza.corpus.models.Document`"""

    #: always filter to item records
    filter_qs = ["item_type_s:document"]

    #: map readable field names to actual solr fields
    field_aliases = {
        "type": "type_s",
        "status": "status_s",
        "shelfmark": "shelfmark_ss",
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

    def keyword_search(self, search_term):
        return self.search(self.keyword_search_qf).raw_query_parameters(
            keyword_query=search_term
        )
