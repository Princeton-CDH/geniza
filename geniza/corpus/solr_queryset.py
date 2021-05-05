from parasolr.django import AliasedSolrQuerySet


class DocumentSolrQuerySet(AliasedSolrQuerySet):
    """':class:`~parasolr.django.AliasedSolrQuerySet` for
    :class:`~geniza.corpus.models.Document`"""

    #: always filter to item records
    filter_qs = ['item_type:document']

    #: map readable field names to actual solr fields
    field_aliases = {
        'type': 'type_s',
        'shelfmark': 'shelfmark_txt',
        'tag': 'tag_txt',
        'description': 'description_t',
        'notes': 'notes_t',
        'needs_review': 'needs_review_t',
        'pgpid': 'pgpid_i'
    }

    # copied from mep; needed?
    # # edismax alias for searching on admin work pseudo-field
    # admin_work_qf = '{!qf=$admin_work_qf pf=$admin_work_pf v=$work_query}'

    # def search_admin_work(self, search_term):
    #     return self.search(self.admin_work_qf) \
    #         .raw_query_parameters(work_query=search_term)
