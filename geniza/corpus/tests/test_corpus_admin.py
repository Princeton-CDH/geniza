from datetime import timedelta, datetime

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.forms import modelform_factory
from django.forms.models import model_to_dict
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains

from geniza.corpus.admin import (DocumentAdmin, DocumentForm,
                                 LanguageScriptAdmin)
from geniza.corpus.models import Document, Fragment, LanguageScript


@pytest.mark.django_db
class TestLanguageScriptAdmin:

    def test_documents(self):
        '''Language script admin should report document usage of script with link'''
        arabic = LanguageScript.objects.create(
            language='Arabic', script='Arabic')
        french = LanguageScript.objects.create(
            language='French', script='Latin')
        english = LanguageScript.objects.create(
            language='English', script='Latin')

        arabic_doc = Document.objects.create()
        arabic_doc.languages.add(arabic)
        french_arabic_doc = Document.objects.create()
        french_arabic_doc.languages.add(arabic, french)

        lang_admin = LanguageScriptAdmin(
            model=LanguageScript, admin_site=admin.site)
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
        arabic_probable_link = lang_admin.probable_documents(
            qs.get(language='Arabic'))
        assert f'?probable_languages__id__exact={arabic.pk}' in arabic_probable_link
        assert '0</a>' in arabic_probable_link

        # add a probable language to our arabic document
        arabic_doc.probable_languages.add(french)
        french_probable_link = lang_admin.probable_documents(
            qs.get(language='French'))
        assert f'?probable_languages__id__exact={french.pk}' in french_probable_link
        assert '1</a>' in french_probable_link


class TestDocumentAdmin:

    def test_rev_dates(self, db, admin_client):
        """Document change form should display first entry/last revision date"""
        # create a testing doc, user, and some log entries
        doc = Document.objects.create()
        doc_ctype = ContentType.objects.get_for_model(doc)
        tj = User.objects.create(username="tj", first_name="Tom",
                                 last_name="Jones", is_superuser=True)
        script = User.objects.get(username=settings.SCRIPT_USERNAME)
        opts = {"object_id": str(doc.pk), "content_type": doc_ctype,
            "object_repr": str(doc)}
        LogEntry.objects.create(**opts,
            user=tj,
            action_flag=ADDITION,
            change_message="Initial data entry",
            action_time=datetime(1995, 3, 11)
        )
        LogEntry.objects.create(**opts,
            user=tj,
            action_flag=CHANGE,
            change_message="Major revision",
            action_time=datetime.today() - timedelta(weeks=1),
        )
        LogEntry.objects.create(**opts,
            user=script,
            action_flag=ADDITION,
            change_message="Imported via script",
            action_time=datetime.today()
        )

        # first and latest revision should be displayed in change form
        response = admin_client.get(reverse("admin:corpus_document_change",
                                      args=(doc.pk,)))
        assertContains(response, '<span class="action-time">March 11, 1995</span>', html=True)
        assertContains(response, '<span class="action-user">Tom Jones</span>', html=True)
        assertContains(response, '<span class="action-msg">Initial data entry</span>', html=True)
        assertContains(response, '<span class="action-time">today</span>', html=True)
        assertContains(response, '<span class="action-user">script</span>', html=True)
        assertContains(response, '<span class="action-msg">Imported via script</span>', html=True)

        # link to view full history should be displayed in change form
        assertContains(response, '<a href="%s">view full history</a>' % \
            reverse("admin:corpus_document_history", args=(doc.pk,)), html=True)

    def test_save_model(self, db):
        '''Ensure that save_as creates a new document and appends a note'''
        fragment = Fragment.objects.create(shelfmark='CUL 123')
        doc = Document.objects.create()
        doc.fragments.add(fragment)

        request_factory = RequestFactory()
        url = reverse('admin:corpus_document_change', args=(doc.id,))

        data = model_to_dict(doc)
        data['_saveasnew'] = 'Save as new'
        for k, v in data.items():
            data[k] = '' if v is None else v
        request = request_factory.post(url, data=data)
        DocumentForm = modelform_factory(Document, exclude=[])
        form = DocumentForm(doc)

        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        # set dates on cloned test doc to confirm they are updated
        lastweek = timezone.now() - timedelta(days=7)
        new_doc = Document.objects.create(created=lastweek,
                                          last_modified=lastweek)
        response = doc_admin.save_model(request, new_doc, form, False)

        # add notes to test existing notes are preserved
        assert Document.objects.count() == 2
        new_doc.notes = 'Test note'
        new_doc.save()
        response = doc_admin.save_model(request, new_doc, form, False)
        assert f'Cloned from {str(doc)}' in new_doc.notes
        assert 'Test note' in new_doc.notes
        assert new_doc.created != lastweek
        assert new_doc.last_modified != lastweek


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
