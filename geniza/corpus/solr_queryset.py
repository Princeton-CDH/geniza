from parasolr.django import AliasedSolrQuerySet


class DocumentSolrQuerySet(AliasedSolrQuerySet):
    """':class:`~parasolr.django.AliasedSolrQuerySet` for
    :class:`~geniza.corpus.models.Document`"""

    #: always filter to item records
    filter_qs = ['item_type:document']

    #: map readable field names to actual solr fields
    field_aliases = {
        'type': 'type_s',
        'status': 'status_s',
        'shelfmark': 'shelfmark_t',
        'tag': 'tag_t',
        'description': 'description_t',
        'notes': 'notes_t',
        'needs_review': 'needs_review_t',
        'pgpid': 'pgpid_i'
    }

    # (adapted from mep)
    # edismax alias for searching on admin document pseudo-field
    admin_doc_qf = '{!edismax qf=$admin_doc_qf pf=$admin_doc_pf v=$doc_query}'

    def admin_search(self, search_term):
        return self.search(self.admin_doc_qf) \
            .raw_query_parameters(doc_query=search_term)
