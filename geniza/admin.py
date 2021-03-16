from django.contrib import admin
from geniza.corpus.models import Document, Fragment

class GenizaAdminSite(admin.AdminSite):
    '''A customized AdminSite to aid PGP workflow'''
    def each_context(self, request):
        '''Provide extra context dictionary to admin site'''
        REVIEW_PREVIEW_MAX = 10

        context = super().each_context(request)

        docs_need_review = Document.objects.exclude(needs_review='').order_by('-last_modified')
        context['docs_review_count'] = len(docs_need_review)
        context['docs_need_review'] = docs_need_review[:REVIEW_PREVIEW_MAX]

        fragments_need_review = Fragment.objects.exclude(needs_review='').order_by('-last_modified')
        context['fragments_review_count'] = len(fragments_need_review)
        context['fragments_need_review'] = fragments_need_review[:REVIEW_PREVIEW_MAX]

        return context

