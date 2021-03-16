import pytest
from django.test.client import RequestFactory
from django.contrib.auth.models import User

from geniza.corpus.models import Document, Fragment
from geniza.admin import GenizaAdminSite

class TestGenizaAdminSite:

    @pytest.mark.django_db
    def test_each_context(self):
        '''Test that data is properly filtered and appended to the admin context'''
        for i in range(15):
            Document.objects.create(needs_review='Test')
            Fragment.objects.create(shelfmark=f'test_{i}', needs_review='Test')
        # create objects that aren't marked for review
        Document.objects.create()
        Fragment.objects.create(shelfmark='No_review')

        # mock the request made by Django's admin
        site = GenizaAdminSite()
        rf = RequestFactory()
        request = rf.get('/admin/')
        request.user = User()  # A user needs to be defined for the request to work
        context = site.each_context(request)

        # ensure that fields are in the context
        expected_fields = ['docs_review_count', 'docs_need_review',
            'fragments_review_count', 'fragments_need_review']
        assert all([field in context for field in expected_fields])

        # ensure that the preview max worked appropriately
        assert len(context['docs_need_review']) == 10
        assert len(context['fragments_need_review']) == 10

        # ensure that the needs_review filter worked appropriately
        assert context['docs_review_count'] == 15
        assert context['fragments_review_count'] == 15
        

