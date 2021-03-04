from django.test import TestCase, RequestFactory
from django.contrib import admin
from django.urls import reverse
from django.forms import modelform_factory

from geniza.corpus.models import LanguageScript, Document, Fragment
from geniza.corpus.admin import LanguageScriptAdmin, DocumentAdmin


class TestLanguageScriptAdmin(TestCase):

    def test_documents(self):
        '''Language script admin should report document usage of script with link'''
        arabic = LanguageScript.objects.create(language='Arabic', script='Arabic')
        french = LanguageScript.objects.create(language='French', script='Latin')
        english = LanguageScript.objects.create(language='English', script='Latin')

        arabic_doc = Document.objects.create()
        arabic_doc.languages.add(arabic)
        french_arabic_doc = Document.objects.create()
        french_arabic_doc.languages.add(arabic, french)

        lang_admin = LanguageScriptAdmin(model=LanguageScript, admin_site=admin.site)
        # retrieve via admin queryset to ensure we have count annotated
        qs = lang_admin.get_queryset(request=None)

        arabic_usage_link = lang_admin.documents(qs.get(language='Arabic'))
        assert f'?languages__id__exact={arabic.pk}' in arabic_usage_link
        assert '2</a>' in arabic_usage_link

        french_usage_link = lang_admin.documents(qs.get(language='French'))
        assert f'?languages__id__exact={french.pk}' in french_usage_link
        assert '1</a>' in french_usage_link

        english_usage_link = lang_admin.documents(qs.get(language='English'))
        assert f'?languages__id__exact={english.pk}' in english_usage_link
        assert '0</a>' in english_usage_link

        # test probable documents
        arabic = qs.get(language='Arabic')
        arabic_probable_link = lang_admin.probable_documents(qs.get(language='Arabic'))
        assert f'?probable_languages__id__exact={arabic.pk}' in arabic_probable_link
        assert '0</a>' in arabic_probable_link

        # add a probable language to our arabic document
        arabic_doc.probable_languages.add(french)
        french_probable_link = lang_admin.probable_documents(qs.get(language='French'))
        assert f'?probable_languages__id__exact={french.pk}' in french_probable_link
        assert '1</a>' in french_probable_link


class TestDocumentAdmin(TestCase):
    def test_save_model(self):
        '''Ensure that save_as creates a new document and appends a note'''
        fragment = Fragment.objects.create(shelfmark='CUL 123')
        doc = Document.objects.create()
        doc.fragments.add(fragment)

        request_factory = RequestFactory()
        url = reverse('admin:corpus_document_change', args=(doc.id,))
        request = request_factory.post(url, data={'_saveasnew': 'Save as new'})
        DocumentForm = modelform_factory(Document, exclude=[])
        form = DocumentForm(doc)

        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        new_doc = Document.objects.create()
        response = doc_admin.save_model(request, new_doc, form, False)

        assert Document.objects.count() == 2
        original_id = doc.id
        cloned_doc = Document.objects.exclude(pk=original_id).first()
        assert 'Cloned from CUL 123' in cloned_doc.notes
