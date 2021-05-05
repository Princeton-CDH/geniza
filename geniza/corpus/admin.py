from django import forms
from django.contrib import admin
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.exceptions import ValidationError
from django.db.models import Count

from django.urls import reverse, resolve
from django.utils.html import format_html
from django.utils import timezone

from geniza.corpus.models import Collection, Document, DocumentType, \
    Fragment, LanguageScript, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.footnotes.admin import FootnoteInline


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('library', 'name', 'lib_abbrev', 'abbrev', 'location')
    search_fields = ('library', 'location', 'name')
    list_display_links = ('library', 'name')


@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = ('language', 'script', 'display_name', 'documents',
                    'probable_documents')

    document_admin_url = 'admin:corpus_document_changelist'
    search_fields = ('language', 'script', 'display_name')

    class Media:
        css = {
            'all': ('css/admin-local.css', )
        }

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .annotate(Count('document', distinct=True),
                      Count('probable_document', distinct=True))

    def documents(self, obj):
        return format_html(
            '<a href="{0}?languages__id__exact={1!s}">{2}</a>',
            reverse(self.document_admin_url), str(obj.id),
            obj.document__count
        )
    documents.short_description = "# documents on which this language appears"
    documents.admin_order_field = 'document__count'

    def probable_documents(self, obj):
        return format_html(
            '<a href="{0}?probable_languages__id__exact={1!s}">{2}</a>',
            reverse(self.document_admin_url), str(obj.id),
            obj.probable_document__count
        )
    probable_documents.short_description = \
        "# documents on which this language might appear (requires confirmation)"
    probable_documents.admin_order_field = 'probable_document__count'


class TextBlockInline(admin.TabularInline):
    model = TextBlock
    autocomplete_fields = ['fragment']
    readonly_fields = ('thumbnail', )
    fields = ('fragment', 'side', 'extent_label', 'multifragment',
              'order', 'thumbnail')


class DocumentForm(forms.ModelForm):

    class Meta:
        model = Document
        exclude = ()

    def clean(self):
        # error if there is any overlap between language and probable lang
        probable_languages = self.cleaned_data['probable_languages']
        if any(plang in self.cleaned_data['languages']
               for plang in probable_languages):
            raise ValidationError(
                'The same language cannot be both probable and definite.')
        # check for unknown as probable here, since autocomplete doesn't
        # honor limit_choices_to option set on thee model
        if any(plang.language == 'Unknown' for plang in probable_languages):
            raise ValidationError(
                '"Unknown" is not allowed for probable language.')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentForm
    list_display = (
        'id',
        'shelfmark', 'description', 'doctype',
        'tag_list', 'all_languages', 'is_textblock',
        'last_modified',
        'is_public'
    )
    readonly_fields = ('created', 'last_modified', 'shelfmark', 'id')
    search_fields = ('fragments__shelfmark', 'tags__name', 'description',
                     'notes', 'needs_review', 'id')
    # TODO include search on edition once we add footnotes
    save_as = True

    list_filter = (
        'doctype', 'languages',
        'probable_languages',
        'status',
        ('textblock__extent_label', admin.EmptyFieldListFilter),
        ('textblock__multifragment', admin.EmptyFieldListFilter),
        ('needs_review', admin.EmptyFieldListFilter)
    )

    fields = (
        ('shelfmark', 'id'),
        'doctype',
        'languages',
        'probable_languages',
        'language_note',
        'description',
        'tags',
        'status',
        'needs_review',
        # edition, translation
        'notes',
        # text block
    )
    autocomplete_fields = ['languages', 'probable_languages']
    # NOTE: autocomplete does not honor limit_choices_to in model
    inlines = [
        TextBlockInline,
        FootnoteInline
    ]

    class Media:
        css = {
            'all': ('css/admin-local.css', )
        }

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .prefetch_related('tags', 'languages', 'textblock_set')  \
            .annotate(shelfmk_all=ArrayAgg('textblock__fragment__shelfmark')) \
            .order_by('shelfmk_all')

    def get_search_results(self, request, queryset, search_term):
        '''Override admin search to use Solr.'''

        # if search term is not blank, filter the queryset via solr search
        if search_term:
            # - use AND instead of OR to get smaller result sets, more
            #  similar to default admin search behavior
            # - return pks for all matching records
            # sqs = DocumentSolrQuerySet().admin_search(search_term) \
            sqs = DocumentSolrQuerySet().search(search_term) \
                .raw_query_parameters(**{'q.op': 'AND'}) \
                .only('pgpid') \
                .get_results(rows=100000)

            pks = [r['pgpid'] for r in sqs]
            # filter queryset by id if there are results
            if sqs:
                queryset = queryset.filter(pk__in=pks)
            else:
                queryset = queryset.none()

        # return queryset, use distinct not needed
        return queryset, False

    def save_model(self, request, obj, form, change):
        '''Customize this model's save_model function and then execute the
         existing admin.ModelAdmin save_model function'''
        if '_saveasnew' in request.POST:
            # Get the ID from the admin URL
            original_pk = resolve(request.path).kwargs['object_id']
            # Get the original object
            original_doc = obj._meta.concrete_model.objects.get(id=original_pk)
            clone_message = f'Cloned from {str(original_doc)}'
            obj.notes = '\n'.join([val for val in (obj.notes, clone_message)
                                   if val])
            # update date created & modified so they are accurate
            # for the new model
            obj.created = timezone.now()
            obj.last_modified = None
        super().save_model(request, obj, form, change)


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    list_display = ('shelfmark', 'collection', 'url',
                    'is_multifragment')
    search_fields = ('shelfmark', 'old_shelfmarks', 'notes', 'needs_review')
    readonly_fields = ('old_shelfmarks', 'created', 'last_modified')
    list_filter = (
        ('collection', admin.RelatedOnlyFieldListFilter),
        'is_multifragment',
        ('url', admin.EmptyFieldListFilter),
        ('needs_review', admin.EmptyFieldListFilter)
    )
    list_editable = ('url',)
    fields = (
        ('shelfmark', 'old_shelfmarks'),
        'collection',
        ('url', 'iiif_url'),
        'is_multifragment',
        'notes',
        'needs_review',
        ('created', 'last_modified')
    )
