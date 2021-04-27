from parasolr import schema


class SolrSchema(schema.SolrSchema):
    '''Solr Schema declaration.'''

    item_type = schema.SolrStringField()

    # have solr automatically track last index time
    last_modified = schema.SolrField('pdate', default='NOW')

    # relying on dynamic fields for everything else; see index_data
    # methods and solr queryset aliases for specifics

    #: copy fields for facets and variant search options
    copy_fields = {}
