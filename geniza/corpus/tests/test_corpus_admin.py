from django.test import TestCase
from django.contrib import admin

from geniza.corpus.models import LanguageScript, Document
from geniza.corpus.admin import LanguageScriptAdmin


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
        assert f'languages__id__exact={arabic.pk}' in arabic_usage_link
        assert '2</a>' in arabic_usage_link

        french_usage_link = lang_admin.documents(qs.get(language='French'))
        assert f'languages__id__exact={french.pk}' in french_usage_link
        assert '1</a>' in french_usage_link

        english_usage_link = lang_admin.documents(qs.get(language='English'))
        assert f'languages__id__exact={english.pk}' in english_usage_link
        assert '0</a>' in english_usage_link
