import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models.query import EmptyQuerySet
from django.forms import modelform_factory
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from pytest_django.asserts import assertContains, assertNotContains

from geniza.corpus.admin import (
    DocumentAdmin,
    DocumentForm,
    FragmentAdmin,
    FragmentTextBlockInline,
    HasTranscriptionListFilter,
    LanguageScriptAdmin,
)
from geniza.corpus.models import (
    Collection,
    Document,
    DocumentType,
    Fragment,
    LanguageScript,
    TextBlock,
)
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


@pytest.mark.django_db
class TestLanguageScriptAdmin:
    def test_documents(self):
        """Language script admin should report document usage of script with link"""
        arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
        french = LanguageScript.objects.create(language="French", script="Latin")
        english = LanguageScript.objects.create(language="English", script="Latin")

        arabic_doc = Document.objects.create()
        arabic_doc.languages.add(arabic)
        french_arabic_doc = Document.objects.create()
        french_arabic_doc.languages.add(arabic, french)

        lang_admin = LanguageScriptAdmin(model=LanguageScript, admin_site=admin.site)
        # retrieve via admin queryset to ensure we have count annotated
        qs = lang_admin.get_queryset(request=None)

        arabic_usage_link = lang_admin.documents(qs.get(language="Arabic"))
        assert f"?languages__id__exact={arabic.pk}" in arabic_usage_link
        assert "2</a>" in arabic_usage_link

        french_usage_link = lang_admin.documents(qs.get(language="French"))
        assert f"?languages__id__exact={french.pk}" in french_usage_link
        assert "1</a>" in french_usage_link

        english_usage_link = lang_admin.documents(qs.get(language="English"))
        assert f"?languages__id__exact={english.pk}" in english_usage_link
        assert "0</a>" in english_usage_link

        # test secondary documents
        arabic = qs.get(language="Arabic")
        arabic_secondary_link = lang_admin.secondary_documents(
            qs.get(language="Arabic")
        )
        assert f"?secondary_languages__id__exact={arabic.pk}" in arabic_secondary_link
        assert "0</a>" in arabic_secondary_link

        # add a secondary language to our arabic document
        arabic_doc.secondary_languages.add(french)
        french_secondary_link = lang_admin.secondary_documents(
            qs.get(language="French")
        )
        assert f"?secondary_languages__id__exact={french.pk}" in french_secondary_link
        assert "1</a>" in french_secondary_link

    def test_get_queryset(self):
        arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
        french = LanguageScript.objects.create(language="French", script="Latin")
        english = LanguageScript.objects.create(language="English", script="Latin")

        lang_admin = LanguageScriptAdmin(model=LanguageScript, admin_site=admin.site)

        request_factory = RequestFactory()
        # simulate request for language script list page
        request = request_factory.post("/admin/corpus/languagescript/")
        qs = lang_admin.get_queryset(request)
        # should have count annotations
        assert hasattr(qs.first(), "document__count")

        # simulate autocomplete request
        request = request_factory.post("/admin/autocomplete/")
        qs = lang_admin.get_queryset(request)
        assert not hasattr(qs.first(), "document__count")


class TestDocumentAdmin:
    def test_rev_dates(self, db, admin_client):
        """Document change form should display first entry/last revision date"""
        # create a testing doc, user, and some log entries
        doc = Document.objects.create()
        doc_ctype = ContentType.objects.get_for_model(doc)
        tj = User.objects.create(
            username="tj", first_name="Tom", last_name="Jones", is_superuser=True
        )
        script = User.objects.get(username=settings.SCRIPT_USERNAME)
        opts = {
            "object_id": str(doc.pk),
            "content_type": doc_ctype,
            "object_repr": str(doc),
        }
        LogEntry.objects.create(
            **opts,
            user=tj,
            action_flag=ADDITION,
            change_message="Initial data entry",
            action_time=timezone.make_aware(datetime(1995, 3, 11)),
        )
        LogEntry.objects.create(
            **opts,
            user=tj,
            action_flag=CHANGE,
            change_message="Major revision",
            action_time=timezone.now() - timedelta(weeks=1),
        )
        LogEntry.objects.create(
            **opts,
            user=script,
            action_flag=ADDITION,
            change_message="Imported via script",
            action_time=timezone.now(),
        )

        # first and latest revision should be displayed in change form
        response = admin_client.get(
            reverse("admin:corpus_document_change", args=(doc.pk,))
        )
        assertContains(
            response, '<span class="action-time">11 March, 1995</span>', html=True
        )
        assertContains(
            response, '<span class="action-user">Tom Jones</span>', html=True
        )
        assertContains(
            response, '<span class="action-msg">Initial data entry</span>', html=True
        )
        assertContains(response, '<span class="action-time">today</span>', html=True)
        assertContains(response, '<span class="action-user">script</span>', html=True)
        assertContains(
            response, '<span class="action-msg">Imported via script</span>', html=True
        )

        # link to view full history should be displayed in change form
        assertContains(
            response,
            '<a href="%s">view full history</a>'
            % reverse("admin:corpus_document_history", args=(doc.pk,)),
            html=True,
        )

    def test_save_model(self, db):
        """Ensure that save_as creates a new document and appends a note"""
        fragment = Fragment.objects.create(shelfmark="CUL 123")
        doc = Document.objects.create()
        doc.fragments.add(fragment)

        request_factory = RequestFactory()
        url = reverse("admin:corpus_document_change", args=(doc.id,))

        data = model_to_dict(doc)
        data["_saveasnew"] = "Save as new"
        for k, v in data.items():
            data[k] = "" if v is None else v
        request = request_factory.post(url, data=data)
        DocumentForm = modelform_factory(Document, exclude=[])
        form = DocumentForm(doc)

        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        # set dates on cloned test doc to confirm they are updated
        lastweek = timezone.now() - timedelta(days=7)
        new_doc = Document.objects.create(created=lastweek, last_modified=lastweek)
        response = doc_admin.save_model(request, new_doc, form, False)

        # add notes to test existing notes are preserved
        assert Document.objects.count() == 2
        new_doc.notes = "Test note"
        new_doc.save()
        response = doc_admin.save_model(request, new_doc, form, False)
        assert f"Cloned from {str(doc)}" in new_doc.notes
        assert "Test note" in new_doc.notes
        assert new_doc.created != lastweek
        assert new_doc.last_modified != lastweek

    def test_get_search_results(self, document, join):
        # index fixture data in solr
        Document.index_items([document, join])
        time.sleep(1)

        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        queryset, needs_distinct = doc_admin.get_search_results(
            Mock(), Document.objects.all(), "bogus"
        )
        assert not queryset.count()
        assert not needs_distinct
        assert isinstance(queryset, EmptyQuerySet)

        queryset, needs_distinct = doc_admin.get_search_results(
            Mock(), Document.objects.all(), "deed of sale"
        )
        assert queryset.count() == 1
        assert isinstance(queryset.first(), Document)

        # empty search term should return all records
        queryset, needs_distinct = doc_admin.get_search_results(
            Mock(), Document.objects.all(), ""
        )
        assert queryset.count() == Document.objects.all().count()

    @pytest.mark.django_db
    def test_export_to_csv(self, document, join):
        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        response = doc_admin.export_to_csv(Mock())
        assert isinstance(response, StreamingHttpResponse)
        # consume the binary streaming content and decode to inspect as str
        content = b"".join([val for val in response.streaming_content]).decode()

        # spot-check that we get expected data
        # - header row
        assert "pgpid,url," in content
        # - some content
        assert str(document.id) in content
        assert document.description in content
        assert str(join.id) in content
        assert join.description in content

    def test_view_old_pgpids(self):
        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        obj = Document()
        # display when there are no pgpids
        assert doc_admin.view_old_pgpids(obj) == "-"

        # display multiple ids
        doc = Document(old_pgpids=[460, 990])
        assert doc_admin.view_old_pgpids(doc) == "460,990"

    def test_document_delete(self, document, admin_client):
        # make sure there is a log entry to trigger the permissions problem
        log_entry = LogEntry.objects.create(
            user_id=1,
            content_type_id=ContentType.objects.get_for_model(document).id,
            object_id=document.id,
            object_repr="test",
            action_flag=CHANGE,
            change_message="test",
        )
        url = reverse("admin:corpus_document_delete", args=(document.id,))
        response = admin_client.get(url)
        assertNotContains(response, "your account doesn't have permission to delete")
        assertNotContains(response, "Log Entry:")

    def test_document_delete_no_log(self, document, admin_client):
        # remove any associated log entries
        document.log_entries.all().delete()
        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        url = reverse("admin:corpus_document_delete", args=(document.id,))
        response = admin_client.get(url)
        # should not error if no log entry is in the deleted objects list
        assert response.status_code == 200

    def test_merge_document(self):
        mockrequest = Mock()
        test_ids = ["50344", "33003", "10100"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = DocumentAdmin(Document, Mock()).merge_documents(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 303
        assert resp["location"].startswith(reverse("admin:document-merge"))
        assert resp["location"].endswith("?ids=%s" % ",".join(test_ids))

        test_ids = ["50344"]
        mockrequest.POST.getlist.return_value = test_ids
        resp = DocumentAdmin(Document, Mock()).merge_documents(mockrequest, Mock())
        assert isinstance(resp, HttpResponseRedirect)
        assert resp.status_code == 302
        assert resp["location"] == reverse("admin:corpus_document_changelist")


@pytest.mark.django_db
class TestDocumentForm:
    def test_clean(self):
        LanguageScript.objects.create(language="Judaeo-Arabic", script="Hebrew")
        LanguageScript.objects.create(language="Unknown", script="Unknown")

        docform = DocumentForm()
        ja = LanguageScript.objects.filter(language="Judaeo-Arabic")
        # return the same option for both, should error
        with pytest.raises(ValidationError) as err:
            docform.cleaned_data = {
                "languages": ja,
                "secondary_languages": ja,
            }
            docform.clean()
        assert "cannot be both primary and secondary" in str(err)


@pytest.mark.django_db
class TestFragmentTextBlockInline:
    def test_document_link(self):
        fragment = Fragment.objects.create(shelfmark="CUL 123")
        doc = Document.objects.create()
        textblock = TextBlock.objects.create(fragment=fragment, document=doc)
        inline = FragmentTextBlockInline(Fragment, admin_site=admin.site)

        doc_link = inline.document_link(textblock)

        assert str(doc.id) in doc_link
        assert str(doc) in doc_link

    def test_document_description(self):
        fragment = Fragment.objects.create(shelfmark="CUL 123")
        test_description = "A medieval poem"
        doc = Document.objects.create(description_en=test_description)
        textblock = TextBlock.objects.create(fragment=fragment, document=doc)
        inline = FragmentTextBlockInline(Fragment, admin_site=admin.site)

        assert test_description == inline.document_description(textblock)


class TestFragmentAdmin:
    @pytest.mark.django_db
    def test_changelist_sort_collection(self, db, admin_client):
        # sorting fragment list on collection should not raise 500 error
        response = admin_client.get(
            reverse("admin:corpus_fragment_changelist") + "?o=2.1"
        )
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_collection_display(self, fragment):
        cul = Collection.objects.create(library="Cambridge", abbrev="CUL")
        fragment.collection = cul
        frag_admin = FragmentAdmin(model=Fragment, admin_site=admin.site)
        assert frag_admin.collection_display(fragment) == cul

    @patch("django.contrib.admin.ModelAdmin.save_model")
    def test_save_model(self, mock_super_save_model):
        frag_admin = FragmentAdmin(model=Fragment, admin_site=admin.site)
        mock_request = Mock()
        mock_obj = Mock()
        frag_admin.save_model(mock_request, mock_obj, Mock(), Mock())
        args, kwargs = mock_super_save_model.call_args
        assert args[1].request == mock_request


class TestHasTranscriptionListFilter:
    def init_filter(self):
        # request, params, model, admin_site
        return HasTranscriptionListFilter(Mock(), {}, Document, DocumentAdmin)

    def test_lookups(self):
        assert self.init_filter().lookups(Mock(), Mock()) == (
            ("yes", "Has transcription"),
            ("no", "No transcription"),
        )

    @pytest.mark.django_db
    def test_queryset(self, document, join, unpublished_editions):
        filter = self.init_filter()

        # no transcription: all documents should be returned
        all_docs = Document.objects.all()
        # no transcription: all documents should be returned
        with patch.object(filter, "value", return_value="no"):
            assert filter.queryset(Mock(), all_docs).count() == 2
        # has transcription: no documents should be returned
        with patch.object(filter, "value", return_value="yes"):
            assert filter.queryset(Mock(), all_docs).count() == 0

        # add a digital edition
        Footnote.objects.create(
            doc_relation=[Footnote.DIGITAL_EDITION],
            source=unpublished_editions,
            content_type_id=ContentType.objects.get(
                app_label="corpus", model="document"
            ).id,
            object_id=document.id,
        )
        # no transcription: one document should be returned
        with patch.object(filter, "value", return_value="no"):
            assert filter.queryset(Mock(), all_docs).count() == 1
        # has transcription: one document should be returned
        with patch.object(filter, "value", return_value="yes"):
            assert filter.queryset(Mock(), all_docs).count() == 1
