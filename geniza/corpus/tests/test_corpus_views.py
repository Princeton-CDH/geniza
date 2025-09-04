import re
from datetime import datetime
from time import sleep
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils.text import Truncator, slugify
from django.utils.timezone import get_current_timezone, make_aware
from parasolr.django import SolrClient
from pytest_django.asserts import assertContains, assertNotContains
from taggit.models import Tag

from geniza.annotations.models import Annotation
from geniza.common.utils import absolutize_url
from geniza.corpus.iiif_utils import EMPTY_CANVAS_ID, new_iiif_canvas
from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet, clean_html
from geniza.corpus.views import (
    DocumentAnnotationListView,
    DocumentDetailView,
    DocumentManifestView,
    DocumentMerge,
    DocumentScholarshipView,
    DocumentSearchView,
    DocumentTranscriptionText,
    SourceAutocompleteView,
    TagMerge,
    old_pgp_edition,
    old_pgp_tabulate_data,
    pgp_metadata_for_old_site,
)
from geniza.entities.models import (
    DocumentPlaceRelation,
    Person,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    Place,
)
from geniza.footnotes.forms import SourceChoiceForm
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


class TestDocumentDetailView:
    def test_page_title(self, document, client):
        """should use doc title as detail view meta title"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        assert response.context["page_title"] == document.title

    def test_page_description(self, document, client):
        """should use truncated doc description as detail view meta description"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        assert response.context["page_description"] == Truncator(
            document.description
        ).words(20)

    def test_get_queryset(self, db, client):
        # Ensure page works normally when not suppressed
        doc = Document.objects.create()
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 200
        assertContains(response, "shelfmark")

        # Test that when status isn't public, it is suppressed
        doc = Document.objects.create(status=Document.SUPPRESSED)
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 404

    def test_permalink(self, document, client):
        """should contain permalink generated from absolutize_url"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        permalink = absolutize_url(document.get_absolute_url()).replace("/en/", "/")
        assertContains(response, f'<a href="{permalink}"')

    def test_past_id_mixin(self, db, client):
        """should redirect from 404 to new pgpid when an old_pgpid is matched"""
        response_404 = client.get(reverse("corpus:document", args=(2,)))
        assert response_404.status_code == 404
        doc = Document.objects.create(id=1, old_pgpids=[2])
        response_301 = client.get(reverse("corpus:document", args=(2,)))
        assert response_301.status_code == 301
        assert response_301.url == absolutize_url(doc.get_absolute_url())

        # Test when pgpid not first in the list
        response_404_notfirst = client.get(reverse("corpus:document", args=(71,)))
        assert response_404_notfirst.status_code == 404
        doc.old_pgpids = [5, 6, 71]
        doc.save()
        response_301_notfirst = client.get(reverse("corpus:document", args=(71,)))
        assert response_301_notfirst.status_code == 301
        assert response_301_notfirst.url == absolutize_url(doc.get_absolute_url())

        # Test partial matching pgpid
        response_404_partialmatch = client.get(reverse("corpus:document", args=(7,)))
        assert response_404_partialmatch.status_code == 404

    def test_get_absolute_url(self, document):
        """should return doc permalink"""
        doc_detail_view = DocumentDetailView()
        doc_detail_view.object = document
        doc_detail_view.kwargs = {"pk": document.pk}
        assert doc_detail_view.get_absolute_url() == absolutize_url(
            document.get_absolute_url()
        )

    def test_last_modified(self, client, document, join):
        """Ensure that the last modified header is set in the HEAD response"""
        SolrClient().update.index([document.index_data()], commit=True)
        response = client.head(document.get_absolute_url())
        assert response["Last-Modified"]
        init_last_modified = response["Last-Modified"]

        # Sleeping is required to ensure that the last modified header is different.
        sleep(1)

        # Ensure that only one last modified header is updated when a document is updated.
        SolrClient().update.index([join.index_data()], commit=True)
        updated_doc_response = client.head(join.get_absolute_url())
        other_doc_response = client.head(document.get_absolute_url())
        assert (
            updated_doc_response["Last-Modified"] != other_doc_response["Last-Modified"]
        )
        assert init_last_modified == other_doc_response["Last-Modified"]

    def test_placeholder_images(self, client, document):
        # mock digital_editions() to return mocked footnote with mocked content_html
        with patch.object(Annotation, "objects") as annotation_qs:
            annotation_qs.filter.return_value.order_by.return_value.values_list.return_value.distinct.return_value = [
                "canvas_1",
                "canvas_2",
            ]
            response = client.get(reverse("corpus:document", args=(document.pk,)))
            placeholders = response.context["images"]
            # should create a dict with canvases as keys and placeholder in values
            assert len(placeholders) == 2
            assert list(placeholders.keys()) == ["canvas_1", "canvas_2"]
            assert placeholders["canvas_1"] == Document.PLACEHOLDER_CANVAS

    def test_get_context_data(self, client, document, source):
        # test default shown/disabled behavior in context data
        response = client.get(reverse("corpus:document", args=(document.pk,)))

        # document has image (via fragment.iiif_url) but no transcription or translation
        assert response.context["default_shown"] == ["images"]
        assert "images" not in response.context["disabled"]
        assert "transcription" in response.context["disabled"]
        assert "translation" in response.context["disabled"]

        # add a transcription
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        response = client.get(reverse("corpus:document", args=(document.pk,)))
        # document has image (via fragment.iiif_url) and transcription, so should show those
        assert "transcription" in response.context["default_shown"]
        assert "images" in response.context["default_shown"]
        assert "transcription" not in response.context["disabled"]
        assert "images" not in response.context["disabled"]
        # should not show translation
        assert "translation" not in response.context["default_shown"]
        assert "translation" in response.context["disabled"]

        # add a translation
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        response = client.get(reverse("corpus:document", args=(document.pk,)))
        # document has image (via fragment.iiif_url) and translation, so should show all three
        assert "translation" in response.context["default_shown"]
        assert "images" in response.context["default_shown"]
        assert "translation" not in response.context["disabled"]
        assert "images" not in response.context["disabled"]
        assert "transcription" in response.context["default_shown"]
        assert "transcription" not in response.context["disabled"]

        # related people and places should be empty querysets
        assert response.context["related_people"].count() == 0
        assert response.context["related_places"].count() == 0

        # add related people
        abu = Person.objects.create(slug="abu-imran")
        ezra = Person.objects.create(slug="ezra-b-hillel")
        nahray = Person.objects.create(slug="nahray")
        (author, _) = PersonDocumentRelationType.objects.get_or_create(name="Author")
        (recipient, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Recipient"
        )
        PersonDocumentRelation.objects.create(
            person=ezra, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=abu, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=nahray, type=author, document=document
        )
        response = client.get(reverse("corpus:document", args=(document.pk,)))
        assert response.context["related_people"].count() == 3
        # should sort alphabetically by type, then slug (name)
        assert response.context["related_people"].first().person.pk == nahray.pk
        assert response.context["related_people"][1].person.pk == abu.pk

        # add related place
        fustat = Place.objects.create(slug="fustat")
        DocumentPlaceRelation.objects.create(place=fustat, document=document)
        assert response.context["related_places"].count() == 1
        assert response.context["related_places"].first().place.pk == fustat.pk

    def test_related_entities(
        self, client, document, person, person_diacritic, person_multiname
    ):
        # add related people
        person.has_page = True
        person.save()
        (author, _) = PersonDocumentRelationType.objects.get_or_create(name="Author")
        (recipient, _) = PersonDocumentRelationType.objects.get_or_create(
            name="Recipient"
        )
        PersonDocumentRelation.objects.create(
            person=person_multiname, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=person_diacritic, type=recipient, document=document
        )
        PersonDocumentRelation.objects.create(
            person=person, type=author, document=document
        )
        # add related place
        fustat = Place.objects.create(slug="fustat")
        DocumentPlaceRelation.objects.create(place=fustat, document=document)

        # should group "recipient" people together and join their names by comma
        response = client.get(reverse("corpus:document", args=(document.pk,)))
        # should be "Halfon, Zed" = recipients
        print(response.content)
        assertContains(response, f"{person_diacritic}, {person_multiname}", html=True)
        # should link to author because has_page=True
        assertContains(
            response, f'<a data-turbo="false" href="{person.get_absolute_url()}">'
        )
        # should link to place
        assertContains(
            response, f'<a data-turbo="false" href="{fustat.get_absolute_url()}">'
        )


@pytest.mark.django_db
def test_old_pgp_tabulate_data():
    legal_doc = DocumentType.objects.get_or_create(name_en="Legal")[0]
    doc = Document.objects.create(id=36, doctype=legal_doc)
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
    TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0])
    doc.fragments.add(frag)
    doc.tags.add("marriage")

    table_iter = old_pgp_tabulate_data(Document.objects.all())
    row = next(table_iter)

    assert "T-S 8J22.21" in row
    assert "#marriage" in row
    assert "recto" in row
    # should not error on document with no old pgpids

    # NOTE: strings are not parsed until after being fed into the csv plugin
    assert legal_doc in row
    assert 36 in row

    doc.old_pgpids = [12345, 67890]
    doc.save()
    table_iter = old_pgp_tabulate_data(Document.objects.all())
    row = next(table_iter)
    assert "12345;67890" in row


@pytest.mark.django_db
def test_old_pgp_edition():
    # Expected behavior:
    # Ed. [fn].
    # Ed. [fn]; also ed. [fn].
    # Ed. [fn]; also ed. [fn]; also trans. [fn].
    # Ed. [fn] [url]; also ed. [fn]; also trans. [fn].

    doc = Document.objects.create()
    assert old_pgp_edition(doc.editions()) == ""

    marina = Creator.objects.create(last_name_en="Rustow", first_name_en="Marina")
    book = SourceType.objects.create(type="Book")
    source = Source.objects.create(source_type=book)
    source.authors.add(marina)
    fn = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source,
        content_object=doc,
    )
    doc.footnotes.add(fn)

    edition_str = old_pgp_edition(doc.editions())
    assert edition_str == f"Ed. {fn.display(old_pgp=True)}"

    source2 = Source.objects.create(title_en="Arabic dictionary", source_type=book)
    fn2 = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source2,
        content_object=doc,
    )
    doc.footnotes.add(fn2)
    edition_str = old_pgp_edition(doc.editions())
    assert edition_str == f"Ed. Arabic dictionary; also ed. Marina Rustow."

    source3 = Source.objects.create(title_en="Geniza Encyclopedia", source_type=book)
    fn_trans = Footnote.objects.create(
        doc_relation=[Footnote.EDITION, Footnote.TRANSLATION],
        source=source3,
        content_object=doc,
    )
    doc.footnotes.add(fn_trans)
    edition_str = old_pgp_edition(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also ed. and trans. Geniza Encyclopedia; also ed. Marina Rustow."
    )

    fn.url = "example.com"
    fn.save()
    edition_str = old_pgp_edition(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also ed. and trans. Geniza Encyclopedia; also ed. Marina Rustow example.com."
    )


@pytest.mark.django_db
def test_pgp_metadata_for_old_site():
    legal_doc = DocumentType.objects.get_or_create(name_en="Legal")[0]
    doc = Document.objects.create(id=36, doctype=legal_doc)
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
    TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0])
    doc.fragments.add(frag)
    doc.tags.add("marriage")

    doc2 = Document.objects.create(status=Document.SUPPRESSED)

    response = pgp_metadata_for_old_site(Mock())
    assert response.status_code == 200

    streaming_content = response.streaming_content
    header = next(streaming_content)
    row1 = next(streaming_content)

    # Ensure no suppressed documents are published
    with pytest.raises(StopIteration):
        row2 = next(streaming_content)

    # Ensure objects have been correctly parsed as strings
    assert b"36" in row1
    assert b"Legal" in row1


class TestDocumentSearchView:
    def test_ignore_suppressed_documents(self, document, empty_solr):
        suppressed_document = Document.objects.create(status=Document.SUPPRESSED)
        Document.index_items([document, suppressed_document])
        SolrClient().update.index([], commit=True)
        # [d.index_data() for d in [document, suppressed_document]], commit=True
        # )

        docsearch_view = DocumentSearchView()
        # mock request with empty keyword search
        docsearch_view.request = Mock()
        docsearch_view.request.GET = {"q": ""}
        qs = docsearch_view.get_queryset()
        result_pgpids = [obj["pgpid"] for obj in qs]
        assert qs.count() == 1
        assert document.id in result_pgpids
        assert suppressed_document.id not in result_pgpids

    def test_get_form_kwargs(self):
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        docsearch_view.get_range_stats = Mock(return_value={})
        # no params
        docsearch_view.request.GET = {}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {
                "mode": "general",
                "sort": "random",
                "regex_field": "transcription",
            },
            "prefix": None,
            "data": {
                "mode": "general",
                "sort": "random",
                "regex_field": "transcription",
            },
            "range_minmax": {},
        }

        # keyword search param
        docsearch_view.request.GET = {"q": "contract"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {
                "mode": "general",
                "sort": "random",
                "regex_field": "transcription",
            },
            "prefix": None,
            "data": {
                "mode": "general",
                "q": "contract",
                "sort": "relevance",
                "regex_field": "transcription",
            },
            "range_minmax": {},
        }

        # sort search param
        docsearch_view.request.GET = {"sort": "scholarship_desc"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {
                "mode": "general",
                "sort": "random",
                "regex_field": "transcription",
            },
            "prefix": None,
            "data": {
                "mode": "general",
                "sort": "scholarship_desc",
                "regex_field": "transcription",
            },
            "range_minmax": {},
        }

        # keyword and sort search params
        docsearch_view.request.GET = {"q": "contract", "sort": "scholarship_desc"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {
                "mode": "general",
                "sort": "random",
                "regex_field": "transcription",
            },
            "prefix": None,
            "data": {
                "mode": "general",
                "q": "contract",
                "sort": "scholarship_desc",
                "regex_field": "transcription",
            },
            "range_minmax": {},
        }

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_get_queryset(self, mock_solr_queryset):
        with patch(
            "geniza.corpus.views.DocumentSolrQuerySet",
            new=self.mock_solr_queryset(
                DocumentSolrQuerySet,
                extra_methods=["admin_search", "keyword_search", "regex_search"],
            ),
        ) as mock_queryset_cls:
            docsearch_view = DocumentSearchView()
            docsearch_view.request = Mock()

            mock_queryset_cls.re_exact_match = DocumentSolrQuerySet.re_exact_match

            # keyword search param
            docsearch_view.request.GET = {"q": "six apartments"}
            docsearch_view.get_range_stats = Mock(return_value={})
            qs = docsearch_view.get_queryset()

            mock_queryset_cls.assert_called_with()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_called_with("six apartments")
            mock_sqs.keyword_search.return_value.highlight.assert_any_call(
                "description", snippets=3, method="unified", requireFieldMatch=True
            )
            mock_sqs.also.assert_called_with("score")
            mock_sqs.also.return_value.order_by.assert_called_with(
                "-score", "shelfmark_natsort"
            )

            # sort search param
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {"sort": "relevance"}
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_not_called()
            # filter called once to limit by status
            assert mock_sqs.filter.call_count == 1
            mock_sqs.filter.assert_called_with(status=Document.STATUS_PUBLIC)
            # order_by should not be called when there is no search query
            mock_sqs.order_by.assert_not_called()

            # sort and keyword search params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {"q": "six apartments", "sort": "relevance"}
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_called_with("six apartments")
            mock_sqs.keyword_search.return_value.also.return_value.order_by.return_value.filter.assert_called_with(
                status=Document.STATUS_PUBLIC
            )
            mock_sqs.keyword_search.return_value.also.return_value.order_by.assert_called_with(
                "-score", "shelfmark_natsort"
            )

            # keyword, sort, and filter search params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {
                "q": "six apartments",
                "sort": "scholarship_desc",
                "doctype": ["Legal"],
                "has_transcription": "on",
                "has_discussion": "on",
                "has_translation": "on",
                "has_image": "on",
                "translation_language": "English",
            }
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_called_with("six apartments")
            # filter by doctype
            mock_sqs.keyword_search.return_value.also.return_value.order_by.return_value.filter.assert_called()
            # also filters that result with next filter (has_transcription)
            mock_sqs.keyword_search.return_value.also.return_value.order_by.return_value.filter.return_value.filter.assert_called()
            mock_sqs.keyword_search.return_value.also.return_value.order_by.assert_called_with(
                "-scholarship_count_i", "shelfmark_natsort"
            )

            # empty params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {"q": "", "sort": ""}
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_not_called()
            args = mock_sqs.order_by.call_args[0]
            assert args[0].startswith("random_")

            # no params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {}
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_not_called()
            args = mock_sqs.order_by.call_args[0]
            assert args[0].startswith("random_")

            # regex search param
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {"q": "six apartments", "mode": "regex"}
            docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.regex_search.assert_called_with(
                "transcription_regex", "six apartments"
            )
            mock_sqs.keyword_search.assert_not_called()
            # should not highlight with parasolr
            mock_sqs.regex_search.return_value.highlight.assert_not_called()

            # no_transcription filter
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {
                "no_transcription": "on",
            }
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.order_by.return_value.filter.assert_called_with(
                has_digital_edition=False
            )

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_get_range_stats(self, mock_solr_queryset):
        with patch(
            "geniza.corpus.views.DocumentSolrQuerySet",
            new=self.mock_solr_queryset(
                DocumentSolrQuerySet, extra_methods=["admin_search", "keyword_search"]
            ),
        ) as mock_queryset_cls:
            # stats = DocumentSolrQuerySet().stats("start_date_i", "end_date_i").get_stats()
            # mock_queryset_cls.return_value.stats.return_value.get_stats.return_value = {
            mock_queryset_cls.return_value.get_stats.return_value = {
                "stats_fields": {
                    "start_dating_i": {"min": None},
                    "end_dating_i": {"max": None},
                }
            }
            docsearch_view = DocumentSearchView()
            docsearch_view.request = Mock()

            # should not error if solr returns none
            stats = docsearch_view.get_range_stats(
                queryset_cls=mock_queryset_cls, field_name="docdate"
            )
            assert stats == {"docdate": (None, None)}
            mock_queryset_cls.return_value.stats.assert_called_with(
                "start_dating_i", "end_dating_i"
            )

            # convert integer date to year
            mock_queryset_cls.return_value.get_stats.return_value = {
                "stats_fields": {
                    "start_dating_i": {"min": 10380101.0},
                    "end_dating_i": {"max": 10421231.0},
                }
            }
            stats = docsearch_view.get_range_stats(
                queryset_cls=mock_queryset_cls, field_name="docdate"
            )
            assert stats == {"docdate": (1038, 1042)}

            # test three-digit year
            mock_queryset_cls.return_value.get_stats.return_value["stats_fields"][
                "start_dating_i"
            ]["min"] = 8430101.0
            stats = docsearch_view.get_range_stats(
                queryset_cls=mock_queryset_cls, field_name="docdate"
            )
            assert stats == {"docdate": (843, 1042)}

    @pytest.mark.usefixtures("mock_solr_queryset")
    @patch("geniza.corpus.views.DocumentSearchView.get_queryset")
    def test_get_context_data(self, mock_get_queryset, rf, mock_solr_queryset):
        with patch(
            "geniza.corpus.views.DocumentSolrQuerySet",
            new=mock_solr_queryset(
                DocumentSolrQuerySet, extra_methods=["admin_search", "keyword_search"]
            ),
        ) as mock_queryset_cls:
            mock_qs = mock_queryset_cls.return_value
            mock_qs.count.return_value = 22
            mock_qs.get_facets.return_value.facet_fields = {}
            # mock_qs.__getitem__.return_value = docsearch_view.queryset

            mock_get_queryset.return_value = mock_qs

            docsearch_view = DocumentSearchView(kwargs={})
            docsearch_view.queryset = mock_qs
            docsearch_view.object_list = mock_qs
            docsearch_view.request = rf.get("/documents/")
            docsearch_view.get_range_stats = Mock(return_value={})

            context_data = docsearch_view.get_context_data()
            assert (
                context_data["highlighting"]
                == context_data["page_obj"].object_list.get_highlighting.return_value
            )
            assert context_data["page_obj"].start_index() == 0
            # NOTE: test paginator isn't initialized properly from queryset count
            # assert context_data["paginator"].count == 22

            # simulate 500 error from solr: get_facets returns {}
            mock_queryset_cls.reset_mock()
            mock_qs = mock_queryset_cls.return_value
            mock_qs.get_facets = Mock(return_value={})
            mock_qs.none = Mock()
            # attribute error should be handled, and use queryset.none().get_facets()
            mock_qs.none.return_value.get_facets.return_value.facet_fields = {}
            # in regex mode, form should get an error message
            assert not len(context_data["form"].errors)
            docsearch_view.request = rf.get("/documents/", {"mode": "regex"})
            context_data = docsearch_view.get_context_data()
            assert len(context_data["form"].errors)

    def test_scholarship_sort(
        self,
        document,
        join,
        empty_solr,
        source,
        twoauthor_source,
        multiauthor_untitledsource,
    ):
        """integration test for sorting by scholarship asc and desc"""

        Footnote.objects.create(
            content_object=join,
            source=source,
            doc_relation=Footnote.EDITION,
        )
        doc_three_records = Document.objects.create(
            description="testing description",
        )
        for src in [source, twoauthor_source, multiauthor_untitledsource]:
            Footnote.objects.create(
                content_object=doc_three_records,
                source=src,
                doc_relation=Footnote.EDITION,
            )

        # ensure solr index is updated with all three test documents
        SolrClient().update.index(
            [
                document.index_data(),  # no scholarship records
                join.index_data(),  # one scholarship record
                doc_three_records.index_data(),  # 3 scholarship records
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()

        # default sort is now random instead of scholarship, so
        # only test sorting explicitly

        # sort by scholarship desc
        docsearch_view.request.GET = {"sort": "scholarship_desc"}
        qs = docsearch_view.get_queryset()
        # should return document with most records first
        assert (
            qs[0]["pgpid"] == doc_three_records.id
        ), "document with most scholarship records returned first"

        # sort by scholarship asc
        docsearch_view.request.GET = {"sort": "scholarship_asc"}
        qs = docsearch_view.get_queryset()
        # should return document with fewest records first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with fewest scholarship records returned first"

        # sort by scholarship asc with query
        docsearch_view.request.GET = {"sort": "scholarship_asc", "q": "testing"}
        qs = docsearch_view.get_queryset()
        # should return 2 documents
        assert qs.count() == 2
        # should return document with fewest records first
        assert (
            qs[0]["pgpid"] == join.id
        ), "document with matching description and fewest scholarship records returned first"

    def test_shelfmark_sort(self, document, multifragment, empty_solr):
        """integration test for sorting by shelfmark"""
        doc2 = Document.objects.create()
        TextBlock.objects.create(document=doc2, fragment=multifragment)
        # create a third document with shelfmark that should come after
        # one of ours only when natural sorting is enabled
        doc3 = Document.objects.create()
        frag3 = Fragment.objects.create(shelfmark="T-S 16.4")
        TextBlock.objects.create(document=doc3, fragment=frag3)
        SolrClient().update.index(
            [
                document.index_data(),  # shelfmark = CUL Add.2586
                doc2.index_data(),  # shelfmark = T-S 16.377
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # sort by shelfmark asc
        docsearch_view.request.GET = {"sort": "shelfmark"}
        qs = docsearch_view.get_queryset()
        # should return document with shelfmark starting with C first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with shelfmark CUL Add.2586 returned first"
        # should return 16.4 before 16.377
        assert (
            qs[1]["pgpid"] == doc3.id
        ), "document with shelfmark T-S 16.4 returned before T-S 16.377"

    def test_relevance_sort_shelfmark_tiebreaker(self, document, empty_solr):
        """integration test for sorting by shelfmark when relevance score is tied"""
        # create a document with shelfmark that should come after CUL Add.2586
        doc2 = Document.objects.create()
        frag3 = Fragment.objects.create(shelfmark="T-S 16.4")
        TextBlock.objects.create(document=doc2, fragment=frag3)
        # add document's tags to doc2 (they need to have the same tags to produce the
        # same relevance score when matching one of the tags)
        doc2.tags.add("bill of sale", "real estate")
        SolrClient().update.index(
            [
                document.index_data(),  # shelfmark = CUL Add.2586
                doc2.index_data(),  # shelfmark = T-S 16.4
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # sort by score desc (relevance)
        docsearch_view.request.GET = {"sort": "relevance", "q": 'tag:"real estate"'}
        qs = docsearch_view.get_queryset()
        # should return document with shelfmark starting with C first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with shelfmark CUL Add.2586 returned first"
        assert (
            qs[1]["pgpid"] == doc2.id
        ), "document with shelfmark T-S 16.4 returned second"

    def test_input_date_sort(self, document, join, empty_solr):
        """Tests for sorting by input date, ascending and descending"""
        # set up log entry for join
        dctype = ContentType.objects.get_for_model(Document)
        team_user = User.objects.get(username=settings.TEAM_USERNAME)
        LogEntry.objects.create(
            user=team_user,
            object_id=str(join.pk),
            object_repr=str(join)[:200],
            content_type=dctype,
            change_message="Initial data entry (spreadsheet), dated 2022",
            action_flag=ADDITION,
            action_time=make_aware(
                datetime(year=2022, month=1, day=1), timezone=get_current_timezone()
            ),
        )
        # update solr index
        SolrClient().update.index(
            [
                document.index_data(),  # input date = 2004
                join.index_data(),  # input date = 2022
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # sort by input date asc
        docsearch_view.request.GET = {"sort": "input_date_asc"}
        qs = docsearch_view.get_queryset()
        # should return document with input date of 2004 first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with input date 2004 returned first"

        # sort by input date desc
        docsearch_view.request.GET = {"sort": "input_date_desc"}
        qs = docsearch_view.get_queryset()
        # should return document with input date of 2022 first
        assert qs[0]["pgpid"] == join.id, "document with input date 2022 returned first"

    def test_doctype_filter(self, document, join, empty_solr):
        """Integration test for document type filter"""
        SolrClient().update.index(
            [
                document.index_data(),  # type = Legal document
                join.index_data(),  # type = Letter
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()

        # no filter
        docsearch_view.request.GET = {}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 2

        # filter by doctype "Legal document"
        docsearch_view.request.GET = {"doctype": ["Legal document"]}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        assert qs[0]["pgpid"] == document.id, "Only legal document returned"

    def test_date_range_filter(self, document, join, empty_solr):
        """Integration test for date range filter"""
        document.doc_date_standard = "1038"
        document.save()
        join.doc_date_standard = "1142-05"
        join.save()
        SolrClient().update.index(
            [
                document.index_data(),
                join.index_data(),
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()

        # filter by date range after 1100
        docsearch_view.request.GET = {"docdate_0": 1100}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        assert qs[0]["pgpid"] == join.id

        # filter by date range before 1050
        docsearch_view.request.GET = {"docdate_1": 1050}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        assert qs[0]["pgpid"] == document.id

        # filter by date range between 1000 and 1100
        docsearch_view.request.GET = {
            "dodate_0": 1000,
            "docdate_1": 1100,
        }
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        assert qs[0]["pgpid"] == document.id

    def test_shelfmark_boost(self, empty_solr, document, multifragment):
        # integration test for shelfmark field boosting
        # in solr configuration
        # - using empty solr fixture to ensure solr is empty when this test starts

        # create a second document with a different shelfmark
        # that references the shelfmark of the first in the description
        related_doc = Document.objects.create(
            description="See also %s" % document.shelfmark
        )
        TextBlock.objects.create(document=related_doc, fragment=multifragment)

        # third document with similar shelfmark
        frag = Fragment.objects.create(
            shelfmark="CUL Add.300",  # fixture has shelfmark CUL Add.2586
        )
        neighbor_doc = Document.objects.create()
        TextBlock.objects.create(document=neighbor_doc, fragment=frag)
        # ensure solr index is updated with all three test documents
        SolrClient().update.index(
            [
                document.index_data(),
                neighbor_doc.index_data(),
                related_doc.index_data(),
            ],
            commit=True,
        )

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # assuming relevance sort is default; update if that changes
        docsearch_view.request.GET = {"q": document.shelfmark, "sort": "relevance"}
        qs = docsearch_view.get_queryset()
        # should return all three documents
        assert qs.count() == 3
        # document with exact match on shelfmark should be returned first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with matching shelfmark returned first"
        # document with full shelfmark should in description should be second
        assert (
            qs[1]["pgpid"] == related_doc.id
        ), "document with shelfmark in description returned second"
        # (document with similar shelfmark is third)

    def test_shelfmark_partialmatch(self, empty_solr, multifragment):
        # integration test for shelfmark indexing with partial matching
        # - using empty solr fixture to ensure solr is empty when this test starts

        # multifragment shelfmark can test for this problem: T-S 16.377
        doc1 = Document.objects.create()
        TextBlock.objects.create(document=doc1, fragment=multifragment)
        # create an arbitrary fragment with similar numeric shelfmark
        folder_fragment = Fragment.objects.create(shelfmark="T-S 16.378")
        doc2 = Document.objects.create()
        TextBlock.objects.create(document=doc2, fragment=folder_fragment)

        # ensure solr index is updated with the two test documents
        SolrClient().update.index(
            [
                doc1.index_data(),
                doc2.index_data(),
            ],
            commit=True,
        )

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # sort doesn't matter in this case
        docsearch_view.request.GET = {"q": "T-S 16"}
        qs = docsearch_view.get_queryset()
        # should return both documents
        assert qs.count() == 2
        resulting_ids = [result["pgpid"] for result in qs]
        assert doc1.id in resulting_ids
        assert doc2.id in resulting_ids

    def test_shelfmark_bigram(self, empty_solr, document):
        # integration test for shelfmark indexing with bigram search
        # - using empty solr fixture to ensure solr is empty when this test starts

        # document shelfmark CUL Add.2586
        SolrClient().update.index([document.index_data()], commit=True)

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # sort doesn't matter in this case; two characters should be enough
        docsearch_view.request.GET = {"q": "25"}
        qs = docsearch_view.get_queryset()
        # should return the document
        assert qs.count() == 1
        resulting_ids = [result["pgpid"] for result in qs]
        assert document.id in resulting_ids

    def test_transcription_bigram(self, empty_solr, annotation):
        # integration test for transcription indexing with bigram search
        # - using empty solr fixture to ensure solr is empty when this test starts

        # annotation with body content "test annotation"
        document = Document.from_manifest_uri(annotation.target_source_manifest_id)
        SolrClient().update.index([document.index_data()], commit=True)

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # sort doesn't matter in this case; two characters minimum
        docsearch_view.request.GET = {"q": "st anno"}
        qs = docsearch_view.get_queryset()
        # should return the document
        assert qs.count() == 1
        resulting_ids = [result["pgpid"] for result in qs]
        assert document.id in resulting_ids

    def test_description_bigram(self, empty_solr, document):
        # integration test for description indexing with bigram search
        # - using empty solr fixture to ensure solr is empty when this test starts

        SolrClient().update.index([document.index_data()], commit=True)

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # sort doesn't matter in this case; two characters minimum
        # al- Mu'tamid
        docsearch_view.request.GET = {"q": "al- Mu'tam"}
        qs = docsearch_view.get_queryset()
        # should return the document
        assert qs.count() == 1
        resulting_ids = [result["pgpid"] for result in qs]
        assert document.id in resulting_ids

    def test_search_shelfmark_override(self, empty_solr, document):
        orig_shelfmark = document.shelfmark
        document.shelfmark_override = "foo 12.34"
        document.save()
        # ensure solr index is updated with this test document
        SolrClient().update.index([document.index_data()], commit=True)

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()

        for shelfmark in [document.shelfmark_override, orig_shelfmark]:
            # keyword search should work
            docsearch_view.request.GET = {"q": shelfmark}
            qs = docsearch_view.get_queryset()
            # should return this document
            assert qs.count() == 1
            assert qs[0]["pgpid"] == document.id

            # fielded search should work too
            docsearch_view.request.GET = {"q": "shelfmark:%s" % shelfmark}
            qs = docsearch_view.get_queryset()
            # should return this document
            assert qs.count() == 1
            assert qs[0]["pgpid"] == document.id

    def test_get_solr_sort(self):
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # default behavior — lookup from dict on the view
        assert (
            docsearch_view.get_solr_sort("relevance")
            == docsearch_view.solr_sort["relevance"]
        )
        # random, no seed set
        random_sort = docsearch_view.get_solr_sort("random")
        assert random_sort.startswith("random_")
        assert int(random_sort.split("_")[1])

        # doc dating without exclude_inferred: should include inferred
        dating_sort = docsearch_view.get_solr_sort("docdate_asc")
        assert dating_sort.startswith("start_dating_")

        # with exclude_inferred: should use start_dating, which is dates without inferred
        dating_sort = docsearch_view.get_solr_sort("docdate_asc", "true")
        assert dating_sort.startswith("start_date_")

    def test_random_page_redirect(self, client):
        # any page of results other than one should redirect to the first page
        docsearch_url = reverse("corpus:document-search")
        response = client.get(docsearch_url, {"sort": "random", "page": 2, "q": "test"})
        # should redirect
        assert response.status_code == 302
        # should preserve any query parameters
        assert response["Location"] == "%s?sort=random&q=test" % docsearch_url

    @pytest.mark.django_db
    def test_dispatch(self, client):
        # test regular response does not redirect
        docsearch_url = reverse("corpus:document-search")
        response = client.get(docsearch_url)
        # should not redirect
        assert response.status_code == 200

    def test_last_modified(self, client, document):
        """Test last modified header for document search"""
        SolrClient().update.index([document.index_data()], commit=True)
        # for now, with random sort as default, no last modified
        response = client.head(reverse("corpus:document-search"))
        assert "Last-Modified" not in response

        # no last-modified if random sort is requested
        response = client.head(reverse("corpus:document-search"), {"sort": "random"})
        assert "Last-Modified" not in response

        # last-modified if random sort is requested
        response = client.head(
            reverse("corpus:document-search"), {"sort": "scholarship_desc"}
        )
        assert response["Last-Modified"]
        init_last_modified = response["Last-Modified"]

        # Sleep before making changes to ensure the last modified header will
        # changes, since last-modified only goes down to the second.
        sleep(1)
        # Ensure that a document being suppressed changes the last modified header
        document.status = Document.SUPPRESSED
        document.save()
        SolrClient().update.index([document.index_data()], commit=True)
        response = client.head(
            reverse("corpus:document-search"), {"sort": "scholarship_desc"}
        )
        new_last_modified = response["Last-Modified"]
        assert new_last_modified != init_last_modified

    def test_exact_match(self, empty_solr, document):
        # integration test for description exact match indexing (description_nostem)
        doc1 = Document.objects.create(description_en="His son sells seashells")
        doc2 = Document.objects.create(
            description_en="Example of something a father sells to his son"
        )
        doc3 = Document.objects.create(description_en="sons selling things")
        SolrClient().update.index(
            [
                document.index_data(),
                doc1.index_data(),
                doc2.index_data(),
                doc3.index_data(),
            ],
            commit=True,
        )

        # first search for just the phrase without doublequotes
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        docsearch_view.request.GET = {"q": "sells to his son", "sort": "relevance"}
        qs = docsearch_view.get_queryset()
        # should return all four documents
        assert qs.count() == 4
        # exact matches should have highest score; shorter description should take precedence
        assert qs[0]["pgpid"] == doc2.id
        assert qs[1]["pgpid"] == document.id

        # now search for an exact match
        docsearch_view.request.GET = {"q": '"sells to his son"', "sort": "relevance"}
        qs = docsearch_view.get_queryset()
        # should only return two documents with exact matches
        # (this won't always be the case, depending on stemming and other processing of the
        # particular words in the query and description, but exact matches should still
        # appear first)
        assert qs.count() == 2
        assert qs[0]["pgpid"] == doc2.id
        assert qs[1]["pgpid"] == document.id

    @pytest.mark.django_db
    def test_ngram_highlighting(self, empty_solr):
        # integration test for solr n-gram size of 2, preserveOriginal (EdgeNGramFilterFactory)
        doc = Document.objects.create(description_en="Abū l-Munā")
        SolrClient().update.index([doc.index_data()], commit=True)
        docsearch_view = DocumentSearchView(kwargs={})
        docsearch_view.request = Mock()
        docsearch_view.request.GET = {"q": "abu l-muna", "sort": "relevance"}
        qs = docsearch_view.get_queryset()
        docsearch_view.object_list = qs
        context_data = docsearch_view.get_context_data()
        # should include the "l" in highlighting
        assert (
            # it will still break elements on whitespace and dash separators
            "<em>Abū</em> <em>l</em>-<em>Munā</em>"
            in context_data["highlighting"]["document.%d" % doc.id]["description"]
        )

    @pytest.mark.django_db
    def test_nostem_boost(self, empty_solr):
        # integration tests for boosting description_nostem to ensure exact matches in description are
        # boosted above partial matches in shelfmark
        harun_doc1 = Document.objects.create(
            description_en="Story in Judaeo-Arabic, mentioning Ḥārūn b. Yaʿīsh and ʿAbd al-ʿAzīz al-Kohen."
        )
        harun_doc2 = Document.objects.create(
            description_en="Letter from Hārūn b. Yaʿqūb, in Tiberias, possibly addressed to Mūsā b. Ismāʿīl b. Sahl. Dating: Likely 11th century. Dealing with the indigo trade. Needs examination."
        )
        yevr_doc1 = Document.objects.create(
            shelfmark_override="Yevr.-Arab. II 1408 + Yevr. Arab. II 1739"
        )
        yevr_doc2 = Document.objects.create(
            shelfmark_override="Yevr.-Arab. II 1739 + Yevr. Arab. II 1408"
        )
        SolrClient().update.index(
            [
                harun_doc1.index_data(),
                harun_doc2.index_data(),
                yevr_doc1.index_data(),
                yevr_doc2.index_data(),
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView(kwargs={})
        docsearch_view.request = Mock()
        docsearch_view.request.GET = {"q": "Harun b. Y*", "sort": "relevance"}
        qs = docsearch_view.get_queryset()
        # should return all four documents
        assert qs.count() == 4
        # should return the exact matches in descriptions first
        assert qs[0]["pgpid"] == harun_doc1.id
        assert qs[1]["pgpid"] == harun_doc2.id
        # ^ tested and this fails when the boost is at its old value (130)

    @pytest.mark.django_db
    def test_cleaned_transcription(self, source, empty_solr):
        # integration tests for cleaned transcription searches
        document = Document.objects.create()
        footnote = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=footnote,
            content={
                # annotation contains brackets and tatweel
                "body": [{"value": "العـ[ـبد]"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        SolrClient().update.index([document.index_data()], commit=True)

        # first search for just the phrase without doublequotes
        docsearch_view = DocumentSearchView(kwargs={})
        docsearch_view.request = Mock()

        # normal search query without the bracket and connectors should match
        docsearch_view.request.GET = {"q": "العبد"}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1

        # exact search without brackets should not match
        docsearch_view.request.GET = {"q": '"العبد"'}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 0

        # exact search with brackets should match AND highlight
        docsearch_view.request.GET = {"q": '"العـ[ـبد]"'}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        docsearch_view.object_list = qs
        context_data = docsearch_view.get_context_data()
        hl = context_data["highlighting"]["document.%d" % document.id]["transcription"]
        assert len(hl) == 1
        assert "<em>العـ[ـبد]</em>" in re.sub(
            r"\s+", "", hl[0]["text"]
        )  # rm solr-added whitespace

        doc2 = Document.objects.create()
        footnote2 = Footnote.objects.create(
            content_object=doc2,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=footnote2,
            content={
                # annotation contains other types of sigla
                "body": [{"value": "פי 〚מ〛תל //דלך// [א]לל[ה] תע/א\לי[ . . . ]"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        SolrClient().update.index([doc2.index_data()], commit=True)
        docsearch_view.request.GET = {"q": "פי מתל דלך אללה תעאלי"}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        docsearch_view.object_list = qs
        context_data = docsearch_view.get_context_data()
        hl = context_data["highlighting"]["document.%d" % doc2.id]["transcription"]
        assert len(hl) == 1
        highlight = re.sub(r"\s+", "", hl[0]["text"])  # rm solr-added whitespace
        # should match on all words
        assert all(
            h in highlight
            for h in ["<em>מ〛תל", "לל[ה]</em>", "<em>תע/א\לי", "<em>דלך"]
        )

        # should remove superfluous characters surrounded by {}
        Annotation.objects.create(
            footnote=footnote2,
            content={
                # annotation contains other types of sigla
                "body": [{"value": "ויב{י}עו"}],
                "target": {"source": {"id": source.uri}},
            },
        )
        SolrClient().update.index([doc2.index_data()], commit=True)
        docsearch_view.request.GET = {"q": "ויבעו"}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1

        # should do the transformation "A | B" --> "A B AB"
        Annotation.objects.create(
            footnote=footnote2,
            content={
                # annotation contains other types of sigla
                "body": [{"value": "להא | בגמיע"}],
                "target": {"source": {"id": source.uri}},
            },
        )
        SolrClient().update.index([doc2.index_data()], commit=True)
        docsearch_view.request.GET = {"q": "להא בגמיע"}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        docsearch_view.request.GET = {"q": "להאבגמיע"}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1

        # and remove | otherwise
        Annotation.objects.create(
            footnote=footnote2,
            content={
                # annotation contains other types of sigla
                "body": [{"value": "ולא|ואן"}],
                "target": {"source": {"id": source.uri}},
            },
        )
        SolrClient().update.index([doc2.index_data()], commit=True)
        docsearch_view.request.GET = {"q": "ולאואן"}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1

    @pytest.mark.django_db
    def test_exact_search_highlight(self, source, empty_solr):
        # integration tests for exact search highlighting
        document = Document.objects.create()
        footnote = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=footnote,
            content={
                # body contains both a partial and an exact match for אלממ
                "body": [{"value": "אלממחה ... אלממ"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        SolrClient().update.index([document.index_data()], commit=True)
        docsearch_view = DocumentSearchView(kwargs={})
        docsearch_view.request = Mock()

        # no double quotes in search, should highlight entire phrase
        docsearch_view.request.GET = {"q": "אלממ"}
        dqs = docsearch_view.get_queryset()
        assert dqs.get_highlighting()[f"document.{document.pk}"]["transcription"][0][
            "text"
        ] == clean_html("<em>אלממחה ... אלממ</em>")

        # double quotes in search, should highlight only the exact match
        docsearch_view.request.GET = {"q": '"אלממ"'}
        dqs = docsearch_view.get_queryset()
        assert dqs.raw_params["hl_query"] == '"אלממ"'
        assert (
            clean_html("<em>אלממ</em>")
            in dqs.get_highlighting()[f"document.{document.pk}"]["transcription"][0][
                "text"
            ]
        )

    @pytest.mark.django_db
    def test_hebrew_prefix_highlight(self, source, empty_solr):
        # test matching for words without searched hebrew prefixes
        document = Document.objects.create()
        footnote = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=footnote,
            content={
                # body contains word מרכב without prefix אל
                "body": [{"value": "מרכב"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        SolrClient().update.index([document.index_data()], commit=True)
        docsearch_view = DocumentSearchView(kwargs={})
        docsearch_view.request = Mock()

        # should match word without prefix, smaller than the entered query
        docsearch_view.request.GET = {"q": "אלמרכב"}
        dqs = docsearch_view.get_queryset()
        assert dqs.get_highlighting()[f"document.{document.pk}"]["transcription"][0][
            "text"
        ] == clean_html("<em>מרכב</em>")

    def test_get_apd_link(self):
        dsv = DocumentSearchView(kwargs={})

        # no arabic or ja: bail out
        assert not dsv.get_apd_link(None)
        assert not dsv.get_apd_link("test")

        # arabic: leave as is
        arabic = "العبد"
        assert dsv.get_apd_link(arabic) == f"{dsv.apd_base_url}{arabic}"

        # JA: translate with regex
        assert dsv.get_apd_link("ואגב") == f"{dsv.apd_base_url}وا[غج]ب"


class TestDocumentScholarshipView:
    def test_page_title(self, document, client, source):
        """should incorporate doc title into scholarship page title"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=(document.id,))
        )
        assert response.context["page_title"] == f"Scholarship on {document.title}"

    def test_page_description(self, document, client, source):
        """should use number of scholarship records as scholarship page description"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=(document.id,))
        )
        assert response.context["page_description"] == f"1 scholarship record"

    def test_get_queryset(self, client, document, source):
        # no footnotes; should 404
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.status_code == 404

        # add a footnote; should return document in context
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.context["document"] == document

        # suppress document; should 404 again
        document.status = Document.SUPPRESSED
        document.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.status_code == 404

    def test_past_id_mixin(self, db, client, source):
        """should redirect from 404 to new pgpid when an old_pgpid is matched"""
        response_404 = client.get(reverse("corpus:document-scholarship", args=[2]))
        assert response_404.status_code == 404
        doc = Document.objects.create(id=1, old_pgpids=[2])
        Footnote.objects.create(content_object=doc, source=source)
        response_301 = client.get(reverse("corpus:document-scholarship", args=[2]))
        assert response_301.status_code == 301
        assert response_301.url == absolutize_url(
            f"{doc.get_absolute_url()}scholarship/"
        )

    def test_get_absolute_url(self, document, source):
        """should return scholarship permalink"""
        Footnote.objects.create(content_object=document, source=source)
        doc_detail_view = DocumentScholarshipView()
        doc_detail_view.object = document
        doc_detail_view.kwargs = {"pk": document.pk}
        assert doc_detail_view.get_absolute_url() == absolutize_url(
            f"{document.get_absolute_url()}scholarship/"
        )

    def test_get_paginate_by(self):
        """Should set pagination to 2 per page"""
        docsearch_view = DocumentSearchView(kwargs={})
        docsearch_view.request = Mock()
        docsearch_view.request.GET = {"per_page": "2"}
        qs = docsearch_view.get_queryset()
        assert docsearch_view.get_paginate_by(qs) == 2


@patch("geniza.corpus.views.IIIFPresentation")
@patch("geniza.corpus.models.IIIFPresentation")
class TestDocumentManifestView:
    view_name = "corpus-uris:document-manifest"

    def test_no_images_no_transcription(
        self,
        mock_view_iiifpres,
        mock_model_iiifpres,
        client,
        document,
        source,
        fragment,
    ):
        # fixture document fragment has iiif, so remove it to test
        fragment.iiif_url = ""
        fragment.save()
        # no iiif or transcription; should 404
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 404

    def test_images_no_transcription(
        self,
        mock_view_iiifpres,
        mock_model_iiifpres,
        client,
        document,
        source,
        fragment,
    ):
        # document fragment has iiif, but no transcription; should return a manifest

        mock_manifest = mock_view_iiifpres.from_url.return_value = (
            mock_model_iiifpres.from_url.return_value
        )
        mock_manifest.label = "Remote content"
        mock_manifest.id = "http://example.io/manifest/1"
        mock_manifest.attribution = (
            "Metadata is public domain; restrictions apply to images."
        )
        mock_manifest.sequences = [
            Mock(canvases=[{"@type": "sc:Canvas", "@id": "urn:m1/c1"}])
        ]

        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 200

        mock_view_iiifpres.from_url.assert_called_with(fragment.iiif_url)

        # should not contain annotation list, since there is no transcription
        assertNotContains(response, "otherContent")
        assertNotContains(response, "sc:AnnotationList")
        # inspect the result as json
        result = response.json()
        assert "Compilation by Princeton Geniza Project." in result["attribution"]
        assert "Additional restrictions may apply." in result["attribution"]
        assert mock_manifest.attribution in result["attribution"]
        # includes canvas from remote manifest
        canvas_1 = result["sequences"][0]["canvases"][0]
        assert canvas_1["@id"] == "urn:m1/c1"
        # includes provenance for canvas
        assert canvas_1["partOf"][0]["@id"] == mock_manifest.id
        assert (
            canvas_1["partOf"][0]["label"]["en"][0]
            == "original source: %s" % mock_manifest.label
        )

    def test_images_no_attribution(
        self, mock_view_iiifpres, mock_model_iiifpres, client, document
    ):
        # manifest has no attribution
        mock_manifest = mock_view_iiifpres.from_url.return_value
        del mock_manifest.attribution  # remove attribution key

        # should only have the default attribution content
        response = client.get(reverse(self.view_name, args=[document.pk]))
        result = response.json()
        assert (
            result["attribution"]
            == '<div class="attribution"><p>Compilation by Princeton Geniza Project.</p><p>Additional restrictions may apply.</p></div>'
        )

    @pytest.mark.django_db
    def test_image_order_override(
        self, mock_view_iiifpres, mock_model_iiifpres, client, fragment
    ):
        # original manifest with canvases in order c1, c2, c3
        mock_manifest = mock_view_iiifpres.from_url.return_value = (
            mock_model_iiifpres.from_url.return_value
        )
        mock_canvases = []
        for i in range(3):
            mock_canvas = MagicMock()
            mock_canvas.id = "urn:m1/c%s" % (i + 1)
            # replicate dict behavior to allow dict(canvas) cast, ensure @id present in result
            mock_dict = {"@id": "urn:m1/c%s" % (i + 1)}
            mock_canvas.keys.return_value = ["@id"]
            mock_canvas.__getitem__.side_effect = mock_dict.__getitem__
            mock_canvases.append(mock_canvas)
        mock_manifest.sequences = [Mock(canvases=mock_canvases)]
        # add image order override to a document
        document = Document.objects.create(
            image_overrides={
                "urn:m1/c2": {"order": 0},
                "urn:m1/c3": {"order": 1},
                "urn:m1/c1": {"order": 2},
            }
        )
        TextBlock.objects.create(document=document, fragment=fragment)
        response = client.get(reverse(self.view_name, args=[document.pk]))
        result = dict(response.json())
        # should be ordered according to override
        assert result["sequences"][0]["canvases"][0]["@id"] == "urn:m1/c2"
        assert result["sequences"][0]["canvases"][1]["@id"] == "urn:m1/c3"
        assert result["sequences"][0]["canvases"][2]["@id"] == "urn:m1/c1"

    def test_no_images_transcription(
        self,
        mock_view_iiifpres,
        mock_model_iiifpres,
        client,
        document,
        source,
        fragment,
    ):
        # remove iiif url from fixture document fragment has iiif
        fragment.iiif_url = ""
        fragment.save()
        # add a footnote with transcription content
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 200

        # should not load any remote manifests
        assert mock_view_iiifpres.from_url.call_count == 0
        # should use empty canvas id
        assertContains(response, EMPTY_CANVAS_ID)
        # should include annotations
        assertContains(response, "otherContent")
        assertContains(response, "sc:AnnotationList")
        # includes url for annotation list
        assertContains(
            response, reverse("corpus-uris:document-annotations", args=[document.pk])
        )

    def test_get_absolute_url(
        self, mock_view_iiifpres, mock_model_iiifpres, document, source
    ):
        """should return manifest permalink"""

        view = DocumentManifestView()
        view.object = document
        view.kwargs = {"pk": document.pk}
        # manifest permalink should not include language code, so build from doc permalink
        assert view.get_absolute_url() == f"{document.permalink}iiif/manifest/"


@patch("geniza.corpus.views.IIIFPresentation")
class TestDocumentAnnotationListView:
    view_name = DocumentAnnotationListView.viewname

    def test_no_transcription(self, mockiifpres, client, document):
        # no iiif or transcription; should 404
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 404

    def test_images_transcription(
        self, mockiifpres, client, document, source, fragment
    ):
        # add a footnote with transcription content
        transcription = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        mock_manifest = mockiifpres.from_url.return_value
        test_canvas = new_iiif_canvas()
        test_canvas.id = "urn:m1/c1"
        test_canvas.width = 300
        test_canvas.height = 250
        mock_manifest.sequences = [Mock(canvases=[test_canvas])]
        annotation_list_url = reverse(self.view_name, args=[document.pk])
        response = client.get(annotation_list_url)
        assert response.status_code == 200
        # inspect result
        data = response.json()
        # each annotation should have a unique id based on annotation list & sequence
        assert data["resources"][0]["@id"].endswith("%s#1" % annotation_list_url)
        # annotation should be attached to canvas by uri with full width & height
        assert data["resources"][0]["on"] == "urn:m1/c1#xywh=0,0,300,250"
        assert (
            data["resources"][0]["resource"] == transcription.iiif_annotation_content()
        )

    def test_no_images_transcription(
        self, mockiifpres, client, document, source, fragment
    ):
        # remove iiif url from fixture document fragment has iiif
        fragment.iiif_url = ""
        fragment.save()
        # add a footnote with transcription content
        footnote = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=footnote,
            content={
                "body": [{"value": "here is my transcription text"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 200

        # should not load any remote manifests
        assert mockiifpres.from_url.call_count == 0
        # should use empty canvas id
        assertContains(response, EMPTY_CANVAS_ID)
        # should include transcription content
        assertContains(response, "here is my transcription text")

    def test_no_shared_resources(
        self, mockiifpres, client, document, source, fragment, join
    ):
        # a list object initialized once in iiif_utils.base_annotation_list
        # was getting reused, resulting in annotations being aggregated
        # and kept every time annotation lists were generated

        # test to confirm the fix

        # remove iiif url from fragment fixture
        fragment.iiif_url = ""
        fragment.save()
        # add a footnote with transcription content to document
        footnote = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=footnote,
            content={
                "body": [{"value": "here is my transcription text"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        # and another to the join document
        digitaledition = Footnote.objects.create(
            content_object=join,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=digitaledition,
            content={
                "body": [{"value": "here is completely different transcription text"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        # request once for document
        client.get(reverse(self.view_name, args=[document.pk]))
        # then request for join doc
        response = client.get(reverse(self.view_name, args=[join.pk]))

        assertNotContains(response, "here is my transcription text")
        assertContains(response, "completely different transcription text")


@pytest.mark.django_db
class TestDocumentTranscriptionText:
    view_name = DocumentTranscriptionText.viewname

    def test_nonexesistent_pgpid(self, client):
        # non-existent pgpid should 404
        assert (
            client.get(
                reverse(self.view_name, kwargs={"pk": 123, "transcription_pk": 456})
            ).status_code
            == 404
        )

    def test_nonexesistent_footnote_id(self, client, document):
        # valid pgpid but non-existent footnote id should 404
        assert (
            client.get(
                reverse(
                    self.view_name, kwargs={"pk": document.pk, "transcription_pk": 123}
                )
            ).status_code
            == 404
        )

    def test_not_edition(self, client, document, source):
        # valid pgpid, valid footnote, but not an edition should 404
        discussion = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DISCUSSION,
        )
        assert (
            client.get(
                reverse(
                    self.view_name,
                    kwargs={"pk": document.pk, "transcription_pk": discussion.pk},
                )
            ).status_code
            == 404
        )

    def test_no_content(self, client, document, source):
        # valid pgpid, valid footnote, but not an edition should 404
        edition = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.EDITION,
        )
        assert (
            client.get(
                reverse(
                    self.view_name,
                    kwargs={"pk": document.pk, "transcription_pk": edition.pk},
                )
            ).status_code
            == 404
        )

    def test_success(self, client, document, source):
        # valid pgpid, valid footnote, but not an edition should 404
        edition = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        Annotation.objects.create(
            footnote=edition,
            content={
                "body": [{"value": "some transcription text"}],
                "target": {
                    "source": {
                        "id": source.uri,
                    }
                },
            },
        )
        response = client.get(
            reverse(
                self.view_name,
                kwargs={"pk": document.pk, "transcription_pk": edition.pk},
            )
        )
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "text/plain; charset=UTF-8"
        content_disposition = response.headers["Content-Disposition"]
        assert content_disposition.startswith("attachment; filename=")
        assert content_disposition.endswith('.txt"')
        # check filename format
        filename = content_disposition.split("=")[1]
        # filename is wrapped in quotes; includes pgpid, shelfmark, author last name
        assert filename.startswith('"PGP%d' % document.pk)
        assert slugify(document.shelfmark) in filename
        assert slugify(source.authorship_set.first().creator.last_name) in filename

        assert response.content == b"some transcription text"


class TestDocumentMergeView:
    def test_get_success_url(self, document):
        merge_view = DocumentMerge()
        merge_view.primary_document = document

        resolved_url = resolve(merge_view.get_success_url())
        assert "admin" in resolved_url.app_names
        assert resolved_url.url_name == "corpus_document_change"

    def test_get_initial(self):
        dmview = DocumentMerge()
        dmview.request = Mock(GET={"ids": "12,23,456,7"})

        initial = dmview.get_initial()
        assert dmview.document_ids == [12, 23, 456, 7]
        # lowest id selected as default primary document
        assert initial["primary_document"] == 7

        # Test when no ideas are provided (a user shouldn't get here,
        #  but shouldn't raise an error.)
        dmview.request = Mock(GET={"ids": ""})
        initial = dmview.get_initial()
        assert dmview.document_ids == []
        dmview.request = Mock(GET={})
        initial = dmview.get_initial()
        assert dmview.document_ids == []

    def test_get_form_kwargs(self):
        dmview = DocumentMerge()
        dmview.request = Mock(GET={"ids": "12,23,456,7"})
        form_kwargs = dmview.get_form_kwargs()
        assert form_kwargs["document_ids"] == dmview.document_ids

    def test_document_merge(self, admin_client, client):
        # Ensure that the document merge view is not visible to public
        response = client.get(reverse("admin:document-merge"))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

        # create test document records to merge
        doc1 = Document.objects.create()
        doc2 = Document.objects.create()

        doc_ids = [doc1.id, doc2.id]
        idstring = ",".join(str(pid) for pid in doc_ids)

        # GET should display choices
        response = admin_client.get(reverse("admin:document-merge"), {"ids": idstring})
        assert response.status_code == 200

        # POST should merge
        merge_url = "%s?ids=%s" % (reverse("admin:document-merge"), idstring)
        response = admin_client.post(
            merge_url,
            {"primary_document": doc1.id, "rationale": "duplicate"},
            follow=True,
        )
        TestCase().assertRedirects(
            response, reverse("admin:corpus_document_change", args=[doc1.id])
        )
        message = list(response.context.get("messages"))[0]
        assert message.tags == "success"
        assert "Successfully merged" in message.message
        assert f"with PGPID {doc1.id}" in message.message

        with patch.object(Document, "merge_with") as mock_merge_with:
            # should pick up rationale notes as parenthetical
            response = admin_client.post(
                merge_url,
                {
                    "primary_document": doc1.id,
                    "rationale": "duplicate",
                    "rationale_notes": "test",
                },
                follow=True,
            )
            mock_merge_with.assert_called_with(ANY, "duplicate (test)", user=ANY)

            # with "other", should use rationale notes as rationale string
            response = admin_client.post(
                merge_url,
                {
                    "primary_document": doc1.id,
                    "rationale": "other",
                    "rationale_notes": "test",
                },
                follow=True,
            )
            mock_merge_with.assert_called_with(ANY, "test", user=ANY)

            # should catch ValidationError and send back to form with error msg
            mock_merge_with.side_effect = ValidationError("test message")
            response = admin_client.post(
                merge_url,
                {
                    "primary_document": doc1.id,
                    "rationale": "duplicate",
                },
                follow=True,
            )
            TestCase().assertRedirects(response, merge_url)
            messages = [str(msg) for msg in list(response.context["messages"])]
            assert "test message" in messages


class TestTagMergeView:
    # adapted from TestDocumentMergeView
    @pytest.mark.django_db
    def test_get_success_url(self):
        merge_view = TagMerge()
        tag = Tag.objects.create(name="test tag")
        merge_view.primary_tag = tag

        resolved_url = resolve(merge_view.get_success_url())
        assert "admin" in resolved_url.app_names
        assert resolved_url.url_name == "taggit_tag_change"

    def test_get_initial(self):
        tmview = TagMerge()
        tmview.request = Mock(GET={"ids": "12,23,456,7"})

        initial = tmview.get_initial()
        assert tmview.tag_ids == [12, 23, 456, 7]
        # lowest id selected as default primary tag
        assert initial["primary_tag"] == 7

        # Test when no ids are provided (a user shouldn't get here,
        # but shouldn't raise an error.)
        tmview.request = Mock(GET={"ids": ""})
        initial = tmview.get_initial()
        assert tmview.tag_ids == []
        tmview.request = Mock(GET={})
        initial = tmview.get_initial()
        assert tmview.tag_ids == []

    def test_get_form_kwargs(self):
        tmview = TagMerge()
        tmview.request = Mock(GET={"ids": "12,23,456,7"})
        form_kwargs = tmview.get_form_kwargs()
        assert form_kwargs["tag_ids"] == tmview.tag_ids

    def test_tag_merge(self, admin_client, client, document, join):
        # Ensure that the tag merge view is not visible to public
        response = client.get(reverse("admin:tag-merge"))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

        # create test tag records to merge, tag some documents
        tag1 = Tag.objects.create(name="16th c")
        tag2 = Tag.objects.create(name="16th century")
        document.tags.add(tag1)
        document.tags.add(tag2)
        old_doc_tagcount = document.tags.count()
        join.tags.add(tag2)

        tag_ids = [tag1.id, tag2.id]
        idstring = ",".join(str(pid) for pid in tag_ids)

        # GET should display choices
        response = admin_client.get(reverse("admin:tag-merge"), {"ids": idstring})
        assert response.status_code == 200

        # POST should merge
        response = admin_client.post(
            "%s?ids=%s" % (reverse("admin:tag-merge"), idstring),
            {"primary_tag": tag1.id},
            follow=True,
        )
        TestCase().assertRedirects(
            response, reverse("admin:taggit_tag_change", args=[tag1.id])
        )
        message = list(response.context.get("messages"))[0]
        assert message.tags == "success"
        assert "Successfully merged" in message.message
        assert f"into {tag1.name}" in message.message

        # tag2 should no longer exist
        assert not Tag.objects.filter(name="16th century").exists()
        assert document.tags.count() == old_doc_tagcount - 1

        # join should be tagged with tag1
        assert tag1 in join.tags.all()

        # should create log entry
        assert LogEntry.objects.filter(
            object_id=tag1.id, change_message__contains=f"merged with {tag2.name}"
        ).exists()


class TestRelatdDocumentview:
    def test_page_title(self, document, join, client, empty_solr):
        """should use doc title in related documents view meta title"""
        Document.index_items([document, join])
        SolrClient().update.index([], commit=True)

        response = client.get(reverse("corpus:related-documents", args=(document.id,)))
        assert (
            response.context["page_title"] == f"Related documents for {document.title}"
        )

    def test_page_description(self, client, document, join, fragment, empty_solr):
        """should use count and pluralization in related documents view meta description"""
        Document.index_items([document, join])
        SolrClient().update.index([], commit=True)

        # "join" fixture = 1 related document
        response = client.get(reverse("corpus:related-documents", args=(document.id,)))
        assert response.context["page_description"] == "1 related document"

        # document on same fragment should add a related document to the other document
        new_doc = Document.objects.create(
            doctype=DocumentType.objects.get_or_create(name_en="Legal")[0],
        )
        TextBlock.objects.create(document=new_doc, fragment=fragment)
        Document.index_items([document, join, new_doc])
        SolrClient().update.index([], commit=True)
        response = client.get(reverse("corpus:related-documents", args=(document.id,)))
        assert response.context["page_description"] == "2 related documents"

    def test_get_context_data(self, document, join, client, empty_solr):
        """should raise 404 on no related, otherwise return inherited context data"""
        # document on new shelfmark should not have any related documents, so should raise 404
        new_doc = Document.objects.create(
            doctype=DocumentType.objects.get_or_create(name_en="Legal")[0],
        )
        new_frag = Fragment.objects.create(shelfmark="fake_shelfmark_related_docs")
        TextBlock.objects.create(document=new_doc, fragment=new_frag)
        Document.index_items([new_doc, document, join])
        SolrClient().update.index([], commit=True)
        response = client.get(reverse("corpus:related-documents", args=(new_doc.id,)))
        assert response.status_code == 404

        # related document view should otherwise inherit context data function from detail view
        related_response = client.get(
            reverse("corpus:related-documents", args=(document.id,))
        )
        doc_response = client.get(reverse("corpus:document", args=(document.id,)))
        assert related_response.status_code == 200
        assert (
            related_response.context["page_includes_transcriptions"]
            == doc_response.context["page_includes_transcriptions"]
        )


class TestDocumentTranscribeView:
    def test_page_title(self, document, source, admin_client):
        """should use doc title in transcription editor meta title"""
        response = admin_client.get(
            reverse("corpus:document-transcribe", args=(document.id, source.pk))
        )
        assert (
            response.context["page_title"] == f"Edit transcription for {document.title}"
        )
        # should use "translation" for translate view
        response = admin_client.get(
            reverse("corpus:document-translate", args=(document.id, source.pk))
        )
        assert (
            response.context["page_title"] == f"Edit translation for {document.title}"
        )

    def test_permissions(self, document, source, client):
        """should redirect to login if user does not have change document permissions"""
        response = client.get(
            reverse("corpus:document-transcribe", args=(document.id, source.pk))
        )
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    def test_get_context_data(self, document, source, admin_client):
        # should pass source URI and source label to page context
        response = admin_client.get(
            reverse("corpus:document-transcribe", args=(document.id, source.pk))
        )
        assert response.context["annotation_config"]["source_uri"] == source.uri
        assert response.context["source_label"] == source.all_authors()

        # since no images/transcription present, and one textblock present,
        # should append two placeholders for use in editor
        assert len(response.context["images"]) == 2
        tb = document.textblock_set.first()
        assert (
            f"{document.permalink}iiif/textblock/{tb.pk}/canvas/1/"
            in response.context["images"]
        )
        assertContains(
            response,
            f"{document.permalink}iiif/textblock/{tb.pk}/canvas/2/",
        )
        assertContains(response, tb.fragment.shelfmark)
        assertContains(response, Document.PLACEHOLDER_CANVAS["image"]["info"])

        # should include text direction
        assert response.context["annotation_config"]["text_direction"] == "rtl"

        # should show transcription and images by default
        assert "transcription" in response.context["default_shown"]
        assert "images" in response.context["default_shown"]
        assert "transcription" not in response.context["disabled"]
        # make sure placeholder can be seen!
        assert "images" not in response.context["disabled"]

        # non-existent source_pk should 404
        response = admin_client.get(
            reverse("corpus:document-transcribe", args=(document.id, 123456789))
        )
        assert response.status_code == 404

        # should include languages for source label in context on translations
        response = admin_client.get(
            reverse("corpus:document-translate", args=(document.id, source.pk))
        )
        assert source.all_languages() in response.context["source_label"]
        # should include translating motivation
        assert (
            response.context["annotation_config"]["secondary_motivation"]
            == "translating"
        )
        # should include text direction
        assert (
            response.context["annotation_config"]["text_direction"]
            == source.languages.first().direction
        )
        # should show translation and images by default
        assert "translation" in response.context["default_shown"]
        assert "images" in response.context["default_shown"]
        assert "translation" not in response.context["disabled"]
        assert "images" not in response.context["disabled"]


class TestSourceAutocompleteView:
    def test_get_queryset(self, source, twoauthor_source):
        source_autocomplete_view = SourceAutocompleteView()
        # mock request with empty search
        source_autocomplete_view.request = Mock()
        source_autocomplete_view.request.GET = {"q": ""}
        qs = source_autocomplete_view.get_queryset()
        # should get two results (all sources)
        assert qs.count() == 2
        # should order twoauthor_source first
        result_pks = [src.pk for src in qs]
        assert source.pk in result_pks and twoauthor_source.pk in result_pks
        assert result_pks.index(twoauthor_source.pk) < result_pks.index(source.pk)

        # should filter on author, case insensitive
        source_autocomplete_view.request.GET = {"q": "orwell"}
        qs = source_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == source.pk

        # should filter on title, case insensitive
        source_autocomplete_view.request.GET = {"q": "programming"}
        qs = source_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == twoauthor_source.pk

        # should filter on combination of title and author, case insensitive
        source_autocomplete_view.request.GET = {"q": "ritchie programming"}
        qs = source_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == twoauthor_source.pk

        # should filter on volume
        twoauthor_source.volume = "XXII"
        twoauthor_source.save()
        source_autocomplete_view.request.GET = {"q": "ritchie programming xxii"}
        qs = source_autocomplete_view.get_queryset()
        assert qs.count() == 1
        assert qs.first().pk == twoauthor_source.pk


class TestDocumentAddTranscriptionView:
    def test_page_title(self, document, admin_client):
        # should use title of document in page title
        response = admin_client.get(
            reverse("corpus:document-add-transcription", args=(document.id,))
        )
        assert (
            response.context["page_title"]
            == f"Add a new transcription for {document.title}"
        )
        # should use translation for that view
        response = admin_client.get(
            reverse("corpus:document-add-translation", args=(document.id,))
        )
        assert (
            response.context["page_title"]
            == f"Add a new translation for {document.title}"
        )

    def test_post(self, document, source, admin_client):
        # should redirect to transcription edit view
        response = admin_client.post(
            reverse("corpus:document-add-transcription", args=(document.id,)),
            {"source": source.pk},
        )
        assert response.status_code == 302
        assert response.url == reverse(
            "corpus:document-transcribe", args=(document.id, source.pk)
        )
        # should redirect to translation edit view in add translation view
        response = admin_client.post(
            reverse("corpus:document-add-translation", args=(document.id,)),
            {"source": source.pk},
        )
        assert response.status_code == 302
        assert response.url == reverse(
            "corpus:document-translate", args=(document.id, source.pk)
        )

    def test_get_context_data(self, document, admin_client):
        # should include SourceChoiceForm
        response = admin_client.get(
            reverse("corpus:document-add-transcription", args=(document.id,))
        )
        assert response.context["form"] == SourceChoiceForm

        # should have page_type "addsource"
        assert response.context["page_type"] == "addsource"

        # should include doc relation in context
        assert response.context["doc_relation"] == "transcription"
