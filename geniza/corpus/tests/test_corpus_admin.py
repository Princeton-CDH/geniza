import pytest

from django.contrib import admin
from django.core.exceptions import ValidationError

from geniza.corpus.models import LanguageScript, Document
from geniza.corpus.admin import LanguageScriptAdmin, DocumentForm


@pytest.mark.django_db
class TestLanguageScriptAdmin:

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


@pytest.mark.django_db
class TestDocumentForm:

    def test_clean(self):
        LanguageScript.objects \
            .create(language='Judaeo-Arabic', script='Hebrew')
        LanguageScript.objects \
            .create(language='Unknown', script='Unknown')

        docform = DocumentForm()
        ja = LanguageScript.objects.filter(language='Judaeo-Arabic')
        # return the same option for both, should error
        with pytest.raises(ValidationError) as err:
            docform.cleaned_data = {
                'languages': ja,
                'probable_languages': ja,
            }
            docform.clean()
        assert 'cannot be both probable and definite' in str(err)

        # return all (including unknown) for probable; should error
        with pytest.raises(ValidationError) as err:
            docform.cleaned_data = {
                'languages': [],
                'probable_languages': LanguageScript.objects.all()
            }
            docform.clean()

        assert '"Unknown" is not allowed for probable language' in str(err)
