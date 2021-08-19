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
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from pytest_django.asserts import assertContains

from geniza.corpus.admin import (
    DocumentAdmin,
    DocumentForm,
    FragmentAdmin,
    FragmentTextBlockInline,
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
            response, '<span class="action-time">March 11, 1995</span>', html=True
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
    def test_tabulate_queryset(self, document):
        # Create all documents
        cul = Collection.objects.create(library="Cambridge", abbrev="CUL")
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21", collection=cul)

        contract = DocumentType.objects.create(name="Contract")
        doc = Document.objects.create(
            description="Business contracts with tables",
            doctype=contract,
            notes="Goitein cards",
            needs_review="demerged",
            status=Document.PUBLIC,
        )
        doc.fragments.add(frag)
        doc.tags.add("table")

        arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
        french = LanguageScript.objects.create(language="French", script="Latin")

        doc.languages.add(arabic)
        doc.secondary_languages.add(french)

        marina = Creator.objects.create(last_name="Rustow", first_name="Marina")
        book = SourceType.objects.create(type="Book")
        source = Source.objects.create(source_type=book)
        source.authors.add(marina)
        footnote = Footnote.objects.create(
            doc_relation=["E"],
            source=source,
            content_type_id=ContentType.objects.get(model="document").id,
            object_id=0,
        )
        doc.footnotes.add(footnote)

        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        doc_qs = Document.objects.all()

        for doc, doc_data in zip(doc_qs, doc_admin.tabulate_queryset(doc_qs)):
            # test some properties
            assert doc.id in doc_data
            assert doc.shelfmark in doc_data
            assert doc.collection in doc_data

            # test callables
            assert doc.all_tags() in doc_data

            # test new functions
            assert f"https://example.com/documents/{doc.id}/" in doc_data
            assert "Public" in doc_data
            assert (
                f"https://example.com/admin/corpus/document/{doc.id}/change/"
                in doc_data
            )
            # initial input should be before last modified
            # (document fixture has a log entry, so should have a first input)
            input_date = doc_data[-6]
            last_modified = doc_data[-5]
            if input_date:
                assert input_date < last_modified, (
                    "expect input date (%s) to be earlier than last modified (%s) [PGPID %s]"
                    % (input_date, last_modified, doc.id)
                )

    @pytest.mark.django_db
    @patch("geniza.corpus.admin.export_to_csv_response")
    def test_export_to_csv(self, mock_export_to_csv_response):
        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        with patch.object(doc_admin, "tabulate_queryset") as tabulate_queryset:
            # if no queryset provided, should use default queryset
            docs = doc_admin.get_queryset(Mock())
            doc_admin.export_to_csv(Mock())
            assert tabulate_queryset.called_once_with(docs)
            # otherwise should respect the provided queryset
            first_person = Document.objects.first()
            doc_admin.export_to_csv(Mock(), first_person)
            assert tabulate_queryset.called_once_with(first_person)

            export_args, export_kwargs = mock_export_to_csv_response.call_args
            # first arg is filename
            csvfilename = export_args[0]
            assert csvfilename.endswith(".csv")
            assert csvfilename.startswith("geniza-documents")
            # should include current date
            assert now().strftime("%Y%m%d") in csvfilename
            headers = export_args[1]
            assert "pgpid" in headers
            assert "description" in headers
            assert "needs_review" in headers

    def test_view_old_pgpids(self):
        doc_admin = DocumentAdmin(model=Document, admin_site=admin.site)
        obj = Mock(old_pgpids=None)
        assert doc_admin.view_old_pgpids(obj) == "-"


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
        doc = Document.objects.create(description=test_description)
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
