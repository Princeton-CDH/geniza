from django.contrib import admin

from geniza.footnotes.models import Source, SourceType, Footnote
from django.contrib.admin import SimpleListFilter

class DocumentRelationsFilter(SimpleListFilter):
    '''A custom filter that allows us to filter sources if any of a source's
     document relations match the given facet'''

    title = 'document relations'
    parameter_name = 'Document relation'

    def lookups(self, request, model_admin):
        return model_admin.model.DOCUMENT_RELATIONS

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(document_relations__contains=self.value())

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = (
        'author', 'title', 
        'get_publish_date_year',
        'edition_number', 
        'join_document_relations'
    )

    search_fields = (
        # TODO: They specifically asked to search on year, is publish_date sufficient?
        'title', 'author__last_name', 'author__first_name', 'publish_date'
    )

    fields = (
        'source_type', 'author', 'title', 'publish_date',
        'edition_number', 'volume', 'page_range', 'document_relations',
        'language'
    )

    list_filter = (
        DocumentRelationsFilter,
    )

    def join_document_relations(self, obj):
        # Casting the multichoice object as a string will return a reader-friendly
        #  comma-delimited list.
        return str(obj.document_relations)
        # TODO: Check get_[field]_display()
        # def get_document_relations_display():
        #       return str(obj.document_relations)
    join_document_relations.short_description = 'Document Relations'

    def get_publish_date_year(self, obj):
        return obj.publish_date.year if obj.publish_date else None
    get_publish_date_year.short_description = 'Year Published'


@admin.register(SourceType)
class SourceTypeAdmin(admin.ModelAdmin):
    pass


