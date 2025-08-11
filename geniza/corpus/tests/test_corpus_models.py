from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
from addict import Dict
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import Resolver404, reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import SafeString
from django.utils.translation import activate, deactivate_all, get_language
from django.utils.translation import override as translation_override
from djiffy.models import Canvas, IIIFImage, Manifest
from modeltranslation.manager import MultilingualQuerySet
from piffle.presentation import IIIFException

from geniza.annotations.models import Annotation
from geniza.corpus.dates import Calendar, PartialDate
from geniza.corpus.models import (
    Collection,
    Dating,
    Document,
    DocumentEventRelation,
    DocumentType,
    Fragment,
    LanguageScript,
    Provenance,
    TextBlock,
)
from geniza.entities.models import (
    DocumentPlaceRelation,
    DocumentPlaceRelationType,
    Event,
    PersonDocumentRelation,
    PersonDocumentRelationType,
    Place,
)
from geniza.footnotes.models import (
    Creator,
    Footnote,
    Source,
    SourceLanguage,
    SourceType,
)


class TestCollection:
    def test_str(self):
        # library only
        lib = Collection(library="British Library", lib_abbrev="BL")
        assert str(lib) == lib.lib_abbrev

        # library + collection
        cul_ts = Collection(
            library="Cambridge UL",
            name="Taylor-Schechter",
            lib_abbrev="CUL",
            abbrev="T-S",
        )
        assert str(cul_ts) == "%s, %s" % (cul_ts.lib_abbrev, cul_ts.abbrev)

        # collection only, no abbreviation
        chapira = Collection(name="Chapira")
        assert str(chapira) == "Chapira"
        # collection abbreviation only
        chapira.abbrev = "chp"
        assert str(chapira) == "chp"

    def test_natural_key(self):
        lib = Collection(library="British Library", abbrev="BL")
        assert lib.natural_key() == ("", "British Library")

        # library + collection
        cul_ts = Collection(
            library="Cambridge UL",
            name="Taylor-Schechter",
            lib_abbrev="CUL",
            abbrev="T-S",
        )
        assert cul_ts.natural_key() == ("Taylor-Schechter", "Cambridge UL")

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        lib = Collection.objects.create(library="British Library", abbrev="BL")
        assert Collection.objects.get_by_natural_key("", "British Library") == lib

        cul_ts = Collection.objects.create(
            library="Cambridge UL",
            name="Taylor-Schechter",
            lib_abbrev="CUL",
            abbrev="T-S",
        )
        assert (
            Collection.objects.get_by_natural_key("Taylor-Schechter", "Cambridge UL")
            == cul_ts
        )

    @pytest.mark.django_db
    def test_library_or_name_required(self):
        # library only
        Collection.objects.create(library="British Library")
        # collection only
        Collection.objects.create(name="Chapira")
        # library + collection
        Collection.objects.create(library="Cambridge UL", name="Taylor-Schechter")

        # one of library or name is required
        with pytest.raises(IntegrityError):
            Collection.objects.create(lib_abbrev="BL")

    @pytest.mark.django_db
    def test_full_name(self):
        # library only
        c = Collection.objects.create(library="British Library")
        assert c.full_name == c.library
        # collection only
        c = Collection.objects.create(name="Chapira")
        assert c.full_name == c.name
        # library + collection
        c = Collection.objects.create(library="Cambridge UL", name="Taylor-Schechter")
        assert c.full_name == f"{c.library}, {c.name}"


class TestLanguageScripts:
    def test_str(self):
        # test display_name overwrite
        lang = LanguageScript(
            display_name="Judaeo-Arabic", language="Judaeo-Arabic", script="Hebrew"
        )
        assert str(lang) == lang.display_name

        # test proper string formatting
        lang = LanguageScript(language="Judaeo-Arabic", script="Hebrew")
        assert str(lang) == "Judaeo-Arabic (Hebrew script)"

    def test_natural_key(self):
        lang = LanguageScript(language="Judaeo-Arabic", script="Hebrew")
        assert lang.natural_key() == (lang.language, lang.script)

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        lang = LanguageScript.objects.create(language="Judaeo-Arabic", script="Hebrew")
        assert (
            LanguageScript.objects.get_by_natural_key(lang.language, lang.script)
            == lang
        )


class TestFragment(TestCase):
    def test_str(self):
        frag = Fragment(shelfmark="TS 1")
        assert str(frag) == frag.shelfmark

    def test_natural_key(self):
        frag = Fragment(shelfmark="TS 1")
        assert frag.natural_key() == (frag.shelfmark,)

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        frag = Fragment.objects.create(shelfmark="TS 1")
        assert Fragment.objects.get_by_natural_key(frag.shelfmark) == frag

    @patch("geniza.corpus.models.IIIFPresentation")
    def test_iiif_thumbnails(self, mockiifpres):
        # no iiif, should use placeholders
        frag = Fragment(shelfmark="TS 1")
        placeholder_thumbnails = frag.iiif_thumbnails()
        assert all(
            img in placeholder_thumbnails
            for img in ["recto-placeholder.svg", "verso-placeholder.svg"]
        )
        assert all(
            label in placeholder_thumbnails
            for label in ['title="recto"', 'title="verso"']
        )
        # test with recto side selected: should add class to recto div, but not verso div
        thumbnails_recto_selected = BeautifulSoup(
            frag.iiif_thumbnails(selected=[0])
        ).find_all("div", {"class": "selected"})

        assert len(thumbnails_recto_selected) == 1
        assert 'title="recto"' in str(thumbnails_recto_selected[0])
        assert 'title="verso"' not in str(thumbnails_recto_selected[0])

        frag.iiif_url = "http://example.co/iiif/ts-1"
        # return simplified part of the manifest we need for this
        mockiifpres.from_url.return_value = Dict(
            {
                "sequences": [
                    {
                        "canvases": [
                            {
                                "images": [
                                    {
                                        "resource": {
                                            "service": {
                                                "id": "http://example.co/iiif/ts-1/00001",
                                            }
                                        }
                                    }
                                ],
                                "label": "1r",
                                "uri": "http://example.co/iiif/ts-1/canvas/00001",
                            },
                            {
                                "images": [
                                    {
                                        "resource": {
                                            "service": {
                                                "id": "http://example.co/iiif/ts-1/00002",
                                            }
                                        }
                                    }
                                ],
                                "label": "1v",
                                "uri": "http://example.co/iiif/ts-1/canvas/00002",
                            },
                        ]
                    }
                ]
            }
        )

        thumbnails = frag.iiif_thumbnails()
        assert (
            '<img src="http://example.co/iiif/ts-1/00001/full/,200/0/default.jpg" loading="lazy"'
            in thumbnails
        )
        assert 'title="1r"' in thumbnails
        assert 'title="1v"' in thumbnails
        assert isinstance(thumbnails, SafeString)

        # test with verso side selected: should add class to 1v div, but not 1r div
        thumbnails_recto_selected = BeautifulSoup(
            frag.iiif_thumbnails(selected=[1])
        ).find_all("div", {"class": "selected"})

        assert len(thumbnails_recto_selected) == 1
        assert 'title="1v"' in str(thumbnails_recto_selected[0])
        assert 'title="1r"' not in str(thumbnails_recto_selected[0])

    @pytest.mark.django_db
    @patch("geniza.corpus.models.GenizaManifestImporter")
    def test_iiif_images_locally_cached_manifest(self, mock_manifestimporter):
        # fragment with a locally cached manifest
        frag = Fragment(shelfmark="TS 1")
        frag.iiif_url = "http://example.io/manifests/1"
        frag.manifest = Manifest.objects.create(uri=frag.iiif_url, short_id="m")

        mock_manifestimporter.return_value.import_paths.return_value = [frag.manifest]
        # canvas with image and label
        Canvas.objects.create(
            manifest=frag.manifest,
            label="fake image",
            iiif_image_id="http://example.co/iiif/ts-1/00001",
            short_id="c",
            order=1,
        )
        frag.save()
        # should return one IIIFImage and one label
        (images, labels, _) = frag.iiif_images()
        assert len(images) == 1
        assert isinstance(images[0], IIIFImage)
        assert len(labels) == 1
        assert labels[0] == "fake image"

    @pytest.mark.django_db
    @patch("geniza.corpus.models.GenizaManifestImporter")
    def test_iiif_images_iiifexception(self, mock_manifestimporter):
        # patch IIIFPresentation.from_url to always raise IIIFException
        with patch("geniza.corpus.models.IIIFPresentation") as mock_iiifpresentation:
            mock_iiifpresentation.from_url = Mock()
            mock_iiifpresentation.from_url.side_effect = IIIFException
            mock_manifestimporter.return_value.import_paths.return_value = []
            frag = Fragment(shelfmark="TS 1")
            frag.iiif_url = "http://example.io/manifests/1"
            frag.save()
            # should log at level WARN
            with self.assertLogs(level="WARN"):
                frag.iiif_images()
                mock_iiifpresentation.from_url.assert_called()

    @pytest.mark.django_db
    @patch("geniza.corpus.models.GenizaManifestImporter")
    def test_attribution(self, mock_manifestimporter):
        # fragment with no manifest
        frag = Fragment(shelfmark="TS 1")
        assert not frag.attribution

        # fragment with a locally cached manifest
        frag = Fragment(shelfmark="TS 2")
        frag.iiif_url = "http://example.io/manifests/2"
        # manifest with an attribution
        frag.manifest = Manifest.objects.create(
            uri=frag.iiif_url,
            short_id="m",
            extra_data={"attribution": "Created by a person"},
        )
        mock_manifestimporter.return_value.import_paths.return_value = [frag.manifest]
        frag.save()
        assert frag.attribution == "Created by a person"

        # should strip out CUDL metadata sentence
        frag.manifest.extra_data = {
            "attribution": "Created by a person. This metadata is published free of restrictions, under the terms of the Creative Commons CC0 1.0 Universal Public Domain Dedication."
        }
        assert frag.attribution == "Created by a person."

    @pytest.mark.django_db
    @patch("geniza.corpus.models.GenizaManifestImporter")
    def test_iiif_provenance(self, mock_manifestimporter):
        # fragment with no manifest
        frag = Fragment(shelfmark="TS 1")
        assert not frag.iiif_provenance

        # fragment with a locally cached manifest
        frag = Fragment(shelfmark="TS 2")
        frag.iiif_url = "http://example.io/manifests/2"
        # manifest with an attribution
        frag.manifest = Manifest.objects.create(
            uri=frag.iiif_url, short_id="m", metadata={"Provenance": ["From a place"]}
        )
        mock_manifestimporter.return_value.import_paths.return_value = [frag.manifest]
        frag.save()
        assert frag.iiif_provenance == "From a place"

    @pytest.mark.django_db
    @patch("geniza.corpus.models.GenizaManifestImporter")
    def test_save(self, mock_manifestimporter):
        frag = Fragment(shelfmark="TS 1")
        frag.save()
        frag.shelfmark = "TS 2"
        frag.save()
        assert frag.old_shelfmarks == "TS 1"
        # should not try to import when there is no url
        assert mock_manifestimporter.call_count == 0

        frag.shelfmark = "TS 3"
        frag.save()

        assert frag.shelfmark == "TS 3"
        assert "TS 1" in frag.old_shelfmarks and "TS 2" in frag.old_shelfmarks

        # Ensure no old shelfmarks are equal to shelfmark
        # (this also makes duplicates impossible)
        frag.shelfmark = "TS 1"
        frag.save()
        assert "TS 1" not in frag.old_shelfmarks

        # double check uniqueness, though the above test is equivalent
        frag.shelfmark = "TS 4"
        frag.save()
        assert len(set(frag.old_shelfmarks.split(";"))) == len(
            frag.old_shelfmarks.split(";")
        )

    @pytest.mark.django_db
    @patch("geniza.corpus.models.GenizaManifestImporter")
    def test_save_import_manifest(self, mock_manifestimporter):
        frag = Fragment(shelfmark="TS 1")
        frag.save()
        frag.shelfmark = "TS 2"
        frag.save()
        mock_manifestimporter.return_value.import_paths.return_value = []
        assert frag.old_shelfmarks == "TS 1"
        # should not try to import when there is no url
        assert mock_manifestimporter.call_count == 0

        # should import when a iiif url is set
        frag.iiif_url = "http://example.io/manifests/1"
        # pre-create manifest that would be imported
        manifest = Manifest.objects.create(uri=frag.iiif_url, short_id="m1")
        mock_manifestimporter.return_value.import_paths.return_value = [manifest]
        frag.save()
        mock_manifestimporter.assert_called_with()
        mock_manifestimporter.return_value.import_paths.assert_called_with(
            [frag.iiif_url]
        )
        # manifest should be set
        assert frag.manifest == manifest

        # should import when iiif url changes, even if manifest is set
        frag.iiif_url = "http://example.io/manifests/2"
        manifest2 = Manifest.objects.create(uri=frag.iiif_url, short_id="m2")
        mock_manifestimporter.return_value.import_paths.return_value = [manifest2]
        frag.save()
        mock_manifestimporter.assert_called_with()
        mock_manifestimporter.return_value.import_paths.assert_called_with(
            [frag.iiif_url]
        )
        # new manifest should be set
        assert frag.manifest == manifest2

        # should not import and should remove manifest when unset
        mock_manifestimporter.reset_mock()
        frag.iiif_url = ""
        frag.save()
        assert mock_manifestimporter.call_count == 0
        assert not frag.manifest

    @pytest.mark.django_db
    @patch("geniza.corpus.models.GenizaManifestImporter")
    @patch("geniza.corpus.models.messages")
    def test_save_import_manifest_error(self, mock_messages, mock_manifestimporter):
        frag = Fragment(shelfmark="TS 1")
        frag.request = Mock()
        # remove any cached manifests
        Manifest.objects.all().delete()
        # return no manifests
        mock_manifestimporter.return_value.import_paths.return_value = []
        # mock manifest does nothing, manifest will be unset
        frag.iiif_url = "something"  # needs to be changed to trigger relevant block
        frag.save()
        mock_messages.warning.assert_called_with(
            frag.request, "Failed to cache IIIF manifest"
        )

        # import causes an error
        mock_manifestimporter.return_value.import_paths.side_effect = IIIFException
        frag.iiif_url = "something else"  # change again to trigger relevant block
        frag.save()
        mock_messages.error.assert_called_with(
            frag.request, "Error loading IIIF manifest"
        )

    def test_clean(self):
        manifest_uri = "http://example.com/manifest/1"
        # strips out redundant uri when present
        frag = Fragment(
            shelfmark="TS 1",
            iiif_url="%(uri)s?manifest=%(uri)s" % {"uri": manifest_uri},
        )
        frag.clean()
        assert frag.iiif_url == manifest_uri

        # does nothing if not present
        frag.iiif_url = manifest_uri
        frag.clean()
        assert frag.iiif_url == manifest_uri


@pytest.mark.django_db
class TestDocumentType:
    def test_str(self):
        """Should use doctype.display_label if available, else use doctype.name"""
        doctype = DocumentType(name_en="Legal")
        assert str(doctype) == doctype.name_en
        doctype.display_label_en = "Legal document"
        assert str(doctype) == "Legal document"

    def test_str_not_en(self):
        # when a translated name is defined without a translated display label,
        # and that language is the active language,
        # we want the translated name, NOT the fallback english display label
        with translation_override("he"):
            doctype = DocumentType(
                name_en="Legal", display_label_en="Legal Document", name_he="מסמך משפטי"
            )
            assert str(doctype) == "מסמך משפטי"

    def test_natural_key(self):
        """Should use name as natural key"""
        doc_type = DocumentType(name_en="SomeType")
        assert len(doc_type.natural_key()) == 1
        assert "SomeType" in doc_type.natural_key()

    def test_get_by_natural_key(self):
        """Should find DocumentType object by name"""
        doc_type = DocumentType(name_en="SomeType")
        doc_type.save()
        assert DocumentType.objects.get_by_natural_key("SomeType") == doc_type

    def test_objects_by_label(self):
        """Should return dict of DocumentType objects keyed on English label"""
        # invalidate cached property (it is computed in other tests in the suite)
        if "objects_by_label" in DocumentType.__dict__:
            # __dict__["objects_by_label"] returns a classmethod
            # __func__ returns a property
            # fget returns the actual cached function
            DocumentType.__dict__["objects_by_label"].__func__.fget.cache_clear()
        # add some new doctypes
        doc_type = DocumentType(name_en="SomeType")
        doc_type.save()
        doc_type_2 = DocumentType(display_label_en="Type2")
        doc_type_2.save()
        # should be able to get a document type by label
        assert isinstance(DocumentType.objects_by_label.get("SomeType"), DocumentType)
        # should match by name_en or display_label_en, depending on what's set
        assert DocumentType.objects_by_label.get("SomeType").pk == doc_type.pk
        assert DocumentType.objects_by_label.get("Type2").pk == doc_type_2.pk


@pytest.mark.django_db
class TestDescriptionAuthorship:
    def test_str(self, document):
        marina = Creator.objects.create(last_name_en="Rustow", first_name_en="Marina")
        document.authors.add(marina)
        authorship = document.descriptionauthorship_set.first()
        assert str(authorship) == '%s, %s description author on "%s"' % (
            marina,
            "1st",
            "PGPID %d" % document.id,
        )


MockImporter = Mock()
# as of djiffy 0.7.2, import paths returns a list of objects
MockImporter.return_value.import_paths.return_value = []


@pytest.mark.django_db
@patch("geniza.corpus.models.GenizaManifestImporter", MockImporter)
class TestDocument:
    def test_shelfmark(self):
        # T-S 8J22.21 + T-S NS J193
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        doc = Document.objects.create()
        doc.fragments.add(frag)
        # single fragment
        assert doc.shelfmark == frag.shelfmark

        # add a second text block with the same fragment
        TextBlock.objects.create(document=doc, fragment=frag)
        # shelfmark should not repeat
        assert doc.shelfmark == frag.shelfmark

        frag2 = Fragment.objects.create(shelfmark="T-S NS J193")
        doc.fragments.add(frag2)
        # multiple fragments: combine shelfmarks
        assert doc.shelfmark == "%s + %s" % (frag.shelfmark, frag2.shelfmark)

        # ensure shelfmark honors order
        doc2 = Document.objects.create()
        TextBlock.objects.create(document=doc2, fragment=frag2, order=1)
        TextBlock.objects.create(document=doc2, fragment=frag, order=2)
        assert doc2.shelfmark == "%s + %s" % (frag2.shelfmark, frag.shelfmark)

        frag3 = Fragment.objects.create(shelfmark="T-S NS J195")
        TextBlock.objects.create(document=doc2, fragment=frag3, order=3, certain=False)
        # ensure that uncertain shelfmarks are not included in str
        assert doc2.shelfmark == "%s + %s" % (frag2.shelfmark, frag.shelfmark)

    def test_shelfmark_override(self, document):
        assert document.shelfmark_display == document.shelfmark
        override = "Foo 1-34"
        document.shelfmark_override = override
        assert document.shelfmark_display == override

    def test_str(self):
        frag = Fragment.objects.create(shelfmark="Or.1081 2.25")
        doc = Document.objects.create()
        doc.fragments.add(frag)
        assert doc.shelfmark in str(doc) and str(doc.id) in str(doc)

        unsaved_doc = Document()
        assert str(unsaved_doc) == "?? (PGPID ??)"

    def test_clean(self):
        doc = Document()
        # no dates; no error
        doc.clean()

        # original date but no calendar — error
        doc.doc_date_original = "480"
        with pytest.raises(ValidationError):
            doc.clean()

        # calendar but no date — error
        doc.doc_date_original = ""
        doc.doc_date_calendar = Calendar.HIJRI
        with pytest.raises(ValidationError):
            doc.clean()

        # both — no error
        doc.doc_date_original = "350"
        doc.clean()

    def test_original_date(self):
        """Should display the historical document date with its calendar name"""
        doc = Document.objects.create(
            doc_date_original="507", doc_date_calendar=Calendar.HIJRI
        )
        assert doc.original_date == "507 Hijrī"
        # with no calendar, just display the date
        doc.doc_date_calendar = ""
        assert doc.original_date == "507"

    def test_collection(self):
        # T-S 8J22.21 + T-S NS J193
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        doc = Document.objects.create()
        doc.fragments.add(frag)
        # single fragment with no collection
        assert doc.collection == ""

        cul = Collection.objects.create(library="Cambridge", abbrev="CUL")
        frag.collection = cul
        frag.save()
        assert doc.collection == cul.abbrev

        # second fragment in the same collection
        frag2 = Fragment.objects.create(shelfmark="T-S NS J193", collection=cul)
        doc.fragments.add(frag2)
        assert doc.collection == cul.abbrev

        # second fragment in a different collection
        jts = Collection.objects.create(library="Jewish Theological", abbrev="JTS")
        frag2.collection = jts
        frag2.save()
        assert doc.collection == "CUL, JTS"

    def test_collections(self):
        aiu = Collection.objects.create(
            library="Alliance Israélite Universelle", abbrev="AIU"
        )
        cul = Collection.objects.create(library="Cambridge", abbrev="CUL")
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21", collection=cul)
        frag2 = Fragment.objects.create(shelfmark="AIU VII.A.23", collection=aiu)
        frag3 = Fragment.objects.create(shelfmark="AIU VII.F.55", collection=aiu)
        doc = Document.objects.create()
        TextBlock.objects.create(document=doc, fragment=frag, order=1)
        TextBlock.objects.create(document=doc, fragment=frag2, order=2)
        TextBlock.objects.create(document=doc, fragment=frag3, order=3)

        # collections should be length 2 because it's a set
        assert len(doc.collections) == 2
        # collections should be listed in textblock order, NOT alphabetically
        colls = list(doc.collections)
        assert colls[0].pk == cul.pk
        assert colls[1].pk == aiu.pk
        assert doc.collection == "CUL, AIU"

    def test_all_languages(self):
        doc = Document.objects.create()
        lang = LanguageScript.objects.create(language="Judaeo-Arabic", script="Hebrew")
        doc.languages.add(lang)
        # single language
        assert doc.all_languages() == str(lang)

        arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
        doc.languages.add(arabic)
        assert doc.all_languages() == "%s, %s" % (arabic, lang)

    def test_all_secondary_languages(self):
        doc = Document.objects.create()
        lang = LanguageScript.objects.create(language="Judaeo-Arabic", script="Hebrew")
        doc.secondary_languages.add(lang)
        # single language
        assert doc.all_secondary_languages() == str(lang)

        arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
        doc.secondary_languages.add(arabic)
        assert doc.all_secondary_languages() == "%s,%s" % (arabic, lang)

    def test_primary_lang_code(self):
        doc = Document.objects.create()
        # no language, no code
        assert doc.primary_lang_code is None

        # single language with code
        lang = LanguageScript.objects.create(
            language="Judaeo-Arabic", script="Hebrew", iso_code="jrb"
        )
        doc.languages.add(lang)
        # delete cached property to recalculate
        del doc.primary_lang_code
        assert doc.primary_lang_code == lang.iso_code

        # second language; no single primary code
        arabic = LanguageScript.objects.create(
            language="Arabic", script="Arabic", iso_code="ar"
        )
        doc.languages.add(arabic)
        del doc.primary_lang_code
        # can't determine primary code
        assert doc.primary_lang_code is None

        # single document with lang but no code
        doc2 = Document.objects.create()
        unknown_lang = LanguageScript.objects.create(
            language="Unknown", script="Hebrew"
        )
        doc2.languages.add(unknown_lang)
        assert doc.primary_lang_code is None

    def test_primary_script(self):
        doc = Document.objects.create()
        # no language, no scrip
        assert doc.primary_script is None

        # single language + script
        lang = LanguageScript.objects.create(
            language="Judaeo-Arabic", script="Hebrew", iso_code="jrb"
        )
        doc.languages.add(lang)
        # delete cached property to recalculate
        del doc.primary_script
        assert doc.primary_script == lang.script

        # second language with the same script
        hebrew = LanguageScript.objects.create(
            language="Hebrew", script="Hebrew", iso_code="he"
        )
        doc.languages.add(hebrew)
        del doc.primary_script
        assert doc.primary_script == lang.script

        # third language, different script; can't calculate
        arabic = LanguageScript.objects.create(
            language="Arabic", script="Arabic", iso_code="ar"
        )
        doc.languages.add(arabic)
        del doc.primary_script
        assert doc.primary_script is None

    def test_formatted_citation(self, document, join, fragment, multifragment):
        # none of these fragments have collections, so they will use shelfmark without
        # full collection names
        assert (
            f"{document.shelfmark}. Available online through the Princeton Geniza Project at"
            in document.formatted_citation
        )
        assert (
            'aria-label="Permalink">%s</a> (accessed' % document.permalink
            in document.formatted_citation
        )
        assert (
            f"{join.shelfmark}. Available online through the Princeton Geniza Project at"
            in join.formatted_citation
        )
        assert (
            'aria-label="Permalink">%s</a> (accessed' % join.permalink
            in join.formatted_citation
        )
        # add some collections with names and test again
        c = Collection.objects.create(
            library="Cambridge University Library", name="Additional Manuscripts"
        )
        fragment.collection = c
        fragment.save()
        c2 = Collection.objects.create(
            library="Cambridge University Library", name="Taylor-Schechter"
        )
        multifragment.collection = c2
        multifragment.save()
        # should include all the collection libraries and names
        assert (
            f"{c.library}, {c.name}, {document.shelfmark}."
            in document.formatted_citation
        )
        assert f"{c.library}, {c.name}" in join.formatted_citation
        assert f"+ {c2.library}, {c2.name}" in join.formatted_citation

        # cite_description = True, but no authorships: same
        document.cite_description = True
        assert f"{document.shelfmark}. Available online" in document.formatted_citation

        # cite_description AND authorships: "description by authors available"
        marina = Creator.objects.create(last_name_en="Rustow", first_name_en="Marina")
        document.authors.add(marina)
        assert (
            f"{document.shelfmark}. Available online" not in document.formatted_citation
        )
        assert f"{document.shelfmark}. Description by" in document.formatted_citation
        assert marina.firstname_lastname() in document.formatted_citation
        assert "available online" in document.formatted_citation

        # test multi-author
        amel = Creator.objects.create(last_name_en="Bensalim", first_name_en="Amel")
        document.authors.add(amel)
        assert (
            f"{marina.firstname_lastname()} and {amel.firstname_lastname()}"
            in document.formatted_citation
        )

        ksenia = Creator.objects.create(last_name_en="Ryzhova", first_name_en="Ksenia")
        document.authors.add(ksenia)
        assert (
            f"{marina.firstname_lastname()}, {amel.firstname_lastname()} and {ksenia.firstname_lastname()}"
            in document.formatted_citation
        )

    def test_all_tags(self):
        doc = Document.objects.create()
        doc.tags.add("marriage", "women")
        tag_list = doc.all_tags()
        # tag order is not reliable, so just check all the pieces
        assert "women" in tag_list
        assert "marriage" in tag_list
        assert ", " in tag_list

    def test_alphabetized_tags(self):
        doc = Document.objects.create()
        # two lowercase tags
        doc.tags.add("women", "marriage")
        alphabetical_tag_list = doc.alphabetized_tags()
        assert alphabetical_tag_list.first().name == "marriage"
        # throw in an uppercase tag
        doc.tags.add("Betical", "alphabet")
        alphabetical_tag_list = doc.alphabetized_tags()
        assert alphabetical_tag_list.first().name == "alphabet"
        assert alphabetical_tag_list[1].name == "Betical"
        # doc with no tags
        doc_no_tags = Document.objects.create()
        assert len(doc_no_tags.alphabetized_tags()) == 0

    def test_is_public(self):
        doc = Document.objects.create()
        assert doc.is_public()
        doc.status = "S"
        assert not doc.is_public()

    def test_get_absolute_url(self):
        doc = Document.objects.create(id=1)
        assert doc.get_absolute_url() == "/en/documents/1/"

    def test_permalink(self):
        """permalink property should be constructed from base url and absolute url, without any language code"""
        current_lang = get_language()

        # if non-default language is active, should stay activate
        activate("he")
        doc = Document.objects.create(id=1)
        site_domain = Site.objects.get_current().domain.rstrip("/")
        # document url should follow directly after site domain,
        # with no language code
        assert f"{site_domain}/documents/1/" in doc.permalink
        # activated language code should persist
        assert get_language() == "he"

        # handle case whre no language active
        deactivate_all()
        assert f"{site_domain}/documents/1/" in doc.permalink

        # reactivate previous default (in case it matters for other tests)
        activate(current_lang)

    @patch("geniza.corpus.models.IIIFPresentation")
    def test_iiif_urls(self, mock_pres):
        # create example doc with two fragments with URLs
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="s1", iiif_url="foo")
        frag2 = Fragment.objects.create(shelfmark="s2", iiif_url="bar")
        TextBlock.objects.create(document=doc, fragment=frag, order=1)
        TextBlock.objects.create(document=doc, fragment=frag2, order=2)
        assert doc.iiif_urls() == ["foo", "bar"]
        # only one URL
        frag2.iiif_url = ""
        frag2.save()
        assert doc.iiif_urls() == ["foo"]
        # no URLs
        frag.iiif_url = ""
        frag.save()
        assert doc.iiif_urls() == []
        # no fragments
        frag.delete()
        frag2.delete()
        assert doc.iiif_urls() == []

    def test_iiif_images(self):
        # Create a document and fragment and a TextBlock to associate them
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0])
        # Mock two IIIF images
        img1 = Mock()
        img2 = Mock()
        # Mock Fragment.iiif_images() to return those two images and two fake labels
        with patch.object(
            Fragment,
            "iiif_images",
            return_value=([img1, img2], ["1r", "1v"], ["canvas1", "canvas2"]),
        ) as mock_frag_iiif:
            images = doc.iiif_images()
            # Should call the mocked function
            mock_frag_iiif.assert_called_once
            # Should return a dict with two objects
            assert len(images) == 2
            assert isinstance(images, dict)
            # dicts should contain the image objects and labels via the mocks
            assert images["canvas1"]["image"] == img1
            assert images["canvas1"]["label"] == "1r"
            assert images["canvas1"]["shelfmark"] == frag.shelfmark
            assert images["canvas2"]["image"] == img2
            assert images["canvas2"]["label"] == "1v"
            assert images["canvas2"]["shelfmark"] == frag.shelfmark

            # Call with filter_side=True
            images = doc.iiif_images(filter_side=True)
            # Should call the mocked function again
            assert mock_frag_iiif.call_count == 2
            # Should return a dict with one entry
            assert len(images) == 1
            # dict should be the recto side, since the TextBlock's side is R
            assert list(images.keys()) == ["canvas1"]

            # call with image_overrides present, reversed order
            doc.image_overrides = {"canvas2": {"order": 0}, "canvas1": {"order": 1}}
            images = doc.iiif_images()
            # img2 should come first now
            assert list(images.keys()) == ["canvas2", "canvas1"]

    def test_iiif_images_with_placeholders(self, source):
        # Create a document and fragment and a TextBlock to associate them
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        tb = TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0])
        # create a digital edition footnote with an associated annotation
        fn = Footnote.objects.create(
            source=source,
            content_object=doc,
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        # annotation should target the textblock on the document
        canvas_str = f"{doc.permalink}iiif/textblock/{tb.pk}/canvas/1/"
        Annotation.objects.create(
            content={
                "body": [{"value": "test annotation", "label": "test label"}],
                "target": {"source": {"id": canvas_str}},
            },
            footnote=fn,
        )
        images = doc.iiif_images(with_placeholders=True)
        assert len(images) == 1
        assert images[canvas_str]["shelfmark"] == frag.shelfmark
        assert images[canvas_str]["label"] == "recto"

        # should not error if the annotation targets a nonexistant textblock
        bad_canvas_str = f"{doc.permalink}iiif/textblock/9999/canvas/2/"
        Annotation.objects.create(
            content={
                "body": [{"value": "test annotation", "label": "test label"}],
                "target": {"source": {"id": bad_canvas_str}},
            },
            footnote=fn,
        )
        # should still successfully populate with an additional placeholder
        images = doc.iiif_images(with_placeholders=True)
        assert len(images) == 2
        # second image should get verso because of /2/
        assert images[bad_canvas_str]["label"] == "verso"

    def test_iiif_images_with_rotation(self, source):
        # Create a document and fragment and a TextBlock to associate them
        # set rotation overrides to 90 and 180
        doc = Document.objects.create(
            image_overrides={"canvas1": {"rotation": 90}, "canvas2": {"rotation": 180}}
        )
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0, 1])
        # Mock two IIIF images
        img1 = Mock()
        img2 = Mock()
        # Mock Fragment.iiif_images() to return those two images and two fake labels
        with patch.object(
            Fragment,
            "iiif_images",
            return_value=([img1, img2], ["1r", "1v"], ["canvas1", "canvas2"]),
        ):
            images = doc.iiif_images()
            # should set rotation by canvas, in order, according to rotation override
            assert images["canvas1"]["rotation"] == 90
            assert images["canvas2"]["rotation"] == 180

    def test_list_thumbnail(self):
        # Create a document and fragment and a TextBlock to associate them
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0])
        img1 = IIIFImage()
        img2 = IIIFImage()
        # Mock Fragment.iiif_images() to return those two images and two fake labels
        with patch.object(
            Fragment,
            "iiif_images",
            return_value=([img1, img2], ["1r", "1v"], ["canvas1", "canvas2"]),
        ):
            thumb = doc.list_thumbnail()
            # should get a thumbnail for the first image at 60x60
            assert 'height="60"' in thumb
            # should only produce img tags for the first of the two images
            assert 'data-canvas="canvas1"' in thumb
            assert 'data-canvas="canvas2"' not in thumb

    def test_admin_thumbnails(self):
        # Create a document and fragment and a TextBlock to associate them
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0])
        # Mock two IIIF images, mock their size functions
        img1 = Mock()
        img1.size.return_value.rotation.return_value = "/img1.jpg"
        img2 = Mock()
        img2.size.return_value.rotation.return_value = "/img2.jpg"
        # Mock Fragment.iiif_images() to return those two images and two fake labels
        with patch.object(
            Fragment,
            "iiif_images",
            return_value=([img1, img2], ["1r", "1v"], ["canvas1", "canvas2"]),
        ):
            thumbs = doc.admin_thumbnails()
            # should call Fragment.admin_thumbnails to produce HTML img tags for the two images
            assert '<img src="/img1.jpg"' in thumbs
            assert '<img src="/img2.jpg"' in thumbs
            # should save canvas IDs to data-canvas attribute
            assert 'data-canvas="canvas1"' in thumbs
            assert 'data-canvas="canvas2"' in thumbs
            # should never have any selected
            assert 'class="selected"' not in thumbs

    def test_fragment_urls(self):
        # create example doc with two fragments with URLs
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="s1", url="foo")
        frag2 = Fragment.objects.create(shelfmark="s2", url="bar")
        TextBlock.objects.create(document=doc, fragment=frag, order=1)
        TextBlock.objects.create(document=doc, fragment=frag2, order=2)
        assert doc.fragment_urls() == ["foo", "bar"]
        # only one URL
        frag2.url = ""
        frag2.save()
        assert doc.fragment_urls() == ["foo"]
        # no URLs
        frag.url = ""
        frag.save()
        assert doc.fragment_urls() == []
        # no fragments
        frag.delete()
        frag2.delete()
        assert doc.fragment_urls() == []

    def test_fragments_other_docs_none(self, document):
        assert document.fragments_other_docs() == []

    def test_fragments_other_docs(self, document, join):
        assert document.fragments_other_docs() == [join]

    def test_fragments_other_docs_multiple(self, document, join):
        doc2 = Document.objects.create()
        doc2.fragments.add(join.fragments.first())
        assert all(doc in join.fragments_other_docs() for doc in [doc2, document])

    def test_fragments_other_docs_suppressed(self, document, join):
        join.status = Document.SUPPRESSED
        join.save()
        assert document.fragments_other_docs() == []

    def test_title(self):
        doc = Document.objects.create()
        assert doc.title == "Unknown type: ??"
        legal = DocumentType.objects.get_or_create(name_en="Legal")[0]
        doc.doctype = legal
        doc.save()
        assert doc.title == "Legal document: ??"
        frag = Fragment.objects.create(shelfmark="s1")
        TextBlock.objects.create(document=doc, fragment=frag, order=1)
        assert doc.title == "Legal document: s1"

    def test_has_transcription(self, document, source):
        # doc with no footnotes doesn't have transcription
        assert not document.has_transcription()

        # doc with empty footnote doesn't have transcription
        fn = Footnote.objects.create(content_object=document, source=source)
        assert not document.has_transcription()

        # doc with digital edition footnote does have a transcription
        fn.doc_relation = [Footnote.DIGITAL_EDITION]
        fn.save()
        assert document.has_transcription()

    def test_has_translation(self, document, source):
        # doc with no footnotes doesn't have translation
        assert not document.has_translation()

        # doc with empty footnote doesn't have translation
        fn = Footnote.objects.create(content_object=document, source=source)
        assert not document.has_translation()

        # doc with regular translation footnote doesn't have translation
        fn.doc_relation = [Footnote.TRANSLATION]
        fn.save()
        assert not document.has_translation()

        # doc with digital translation footnote does have a translation
        fn.doc_relation = [Footnote.DIGITAL_TRANSLATION]
        fn.save()
        assert document.has_translation()

    def test_has_image(self, document, fragment):
        # doc with fragment with IIIF url has image
        assert document.has_image()

        # remove IIIF url from fragment; doc should no longer have image
        fragment.iiif_url = ""
        fragment.save()
        assert not document.has_image()

    def test_has_digital_content(self, fragment, source):
        # document with no IIIF or footnotes should not have digital content
        frag = Fragment.objects.create()
        doc = Document.objects.create()
        TextBlock.objects.create(document=doc, fragment=frag, order=1)
        assert not doc.has_digital_content()
        # document from fragment should have IIIF url = digital content
        doc = Document.objects.create()
        TextBlock.objects.create(document=doc, fragment=fragment, order=1)
        assert doc.has_digital_content()
        # document with digital edition = digital content
        doc = Document.objects.create()
        Footnote.objects.create(
            content_object=doc, source=source, doc_relation=Footnote.DIGITAL_EDITION
        )
        assert doc.has_digital_content()
        # document with digital translation = digital content
        doc = Document.objects.create()
        Footnote.objects.create(
            content_object=doc, source=source, doc_relation=Footnote.DIGITAL_TRANSLATION
        )
        assert doc.has_digital_content()

    def test_index_data(self, document):
        index_data = document.index_data()
        assert index_data["id"] == document.index_id()
        assert index_data["item_type_s"] == "document"
        assert index_data["pgpid_i"] == document.pk
        assert index_data["type_s"] == str(document.doctype)
        assert index_data["description_en_bigram"] == document.description
        assert index_data["notes_t"] is None  # no notes
        assert index_data["needs_review_t"] is None  # no review notes
        assert index_data["shelfmark_s"] == document.shelfmark
        for frag in document.fragments.all():
            assert frag.shelfmark in index_data["fragment_shelfmark_ss"]
        for tag in document.tags.all():
            assert tag.name in index_data["tags_ss_lower"]
        assert index_data["status_s"] == "Public"
        assert not index_data["old_pgpids_is"]

        # test with notes and review notes
        document.notes = "FGP stub"
        document.needs_review = "check description"
        index_data = document.index_data()
        assert index_data["notes_t"] == document.notes
        assert index_data["needs_review_t"] == document.needs_review

        # suppressed documents are still indexed,
        # since they need to be searchable in admin
        document.status = Document.SUPPRESSED
        index_data = document.index_data()
        assert index_data["id"] == document.index_id()
        assert "item_type_s" in index_data
        assert index_data["status_s"] == "Suppressed"

        # add old pgpids
        document.old_pgpids = [12345, 9876]
        index_data = document.index_data()
        assert index_data["old_pgpids_is"] == [12345, 9876]

        # no footnotes — all scholarship counts should be zero
        for scholarship_count in [
            "num_editions_i",
            "num_translations_i",
            "num_discussions_i",
            "scholarship_count_i",
        ]:
            assert index_data[scholarship_count] == 0
        assert index_data["scholarship_t"] == []

        # no images - has_image bool should be false
        assert not index_data["has_image_b"]

        # add mock images
        img1 = Mock()
        img1.info.return_value = "http://example.co/iiif/ts-1/00001/info.json"
        img2 = Mock()
        img2.info.return_value = "http://example.co/iiif/ts-1/00002/info.json"
        # Mock Fragment.iiif_images() to return those two images and two fake labels
        with patch.object(
            Fragment,
            "iiif_images",
            return_value=([img1, img2], ["label1", "label2"], ["canvas1", "canvas2"]),
        ):
            index_data = document.index_data()
            # index data should pick up images and labels
            assert index_data["iiif_images_ss"] == [
                "http://example.co/iiif/ts-1/00001",
                "http://example.co/iiif/ts-1/00002",
            ]
            assert index_data["iiif_labels_ss"] == ["label1", "label2"]
            assert index_data["iiif_rotations_is"] == [0, 0]
            assert index_data["has_image_b"] is True

    def test_index_data_rotations(self, document):
        # add image rotation
        document.image_overrides = {
            "canvas1": {"rotation": 90},
            "canvas2": {"rotation": 180},
        }
        # add mock images
        img1 = Mock()
        img1.info.return_value = "http://example.co/iiif/ts-1/00001/info.json"
        img2 = Mock()
        img2.info.return_value = "http://example.co/iiif/ts-1/00002/info.json"
        # Mock Fragment.iiif_images() to return those two images
        with patch.object(
            Fragment,
            "iiif_images",
            # match canvas1 and canvas2 names from image overrides
            return_value=([img1, img2], ["label1", "label2"], ["canvas1", "canvas2"]),
        ):
            index_data = document.index_data()
            # index data should pick up rotation overrides
            assert index_data["iiif_rotations_is"] == [90, 180]

    def test_index_data_footnotes(
        self, document, source, twoauthor_source, multiauthor_untitledsource
    ):
        # digital edition footnote
        edition = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        Annotation.objects.create(
            footnote=edition,
            content={
                "body": [{"value": "transcrip[ti]on lines"}],
            },
        )
        # digital translation footnote
        digital_translation = Footnote.objects.create(
            content_object=document,
            source=source,  # English language source
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        Annotation.objects.create(
            footnote=digital_translation,
            content={
                "body": [{"value": "<ol><li>translation lines</li></ol>"}],
            },
        )
        # other footnotes
        edition2 = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation={Footnote.EDITION, Footnote.TRANSLATION},
        )
        translation = Footnote.objects.create(
            content_object=document,
            source=multiauthor_untitledsource,
            doc_relation=Footnote.TRANSLATION,
        )
        index_data = document.index_data()
        assert index_data["num_editions_i"] == 2  # edition + digital edition
        assert index_data["has_digital_edition_b"] == True
        assert (
            index_data["num_translations_i"] == 3
        )  # 2 translations + 1 digital translation
        assert index_data["has_digital_translation_b"] == True
        assert index_data["scholarship_count_i"] == 3  # unique sources
        assert index_data["text_transcription"] == ["transcrip[ti]on lines"]
        assert index_data["text_translation"] == [
            '<ol><li value="1">translation lines</li></ol>'
        ]
        assert str(source) in index_data["translation_regex_names_ss"]
        assert index_data["translation_regex"] == ["translation lines"]
        assert index_data["translation_languages_ss"] == ["English"]
        assert index_data["translation_language_code_s"] == "en"
        assert index_data["translation_language_direction_s"] == "ltr"

        for note in [edition, edition2, translation, digital_translation]:
            assert note.display() in index_data["scholarship_t"]

    def test_index_data_document_date(self):
        document = Document(
            id=123,
            doc_date_original="5 Elul 5567",
            doc_date_calendar=Calendar.ANNO_MUNDI,
            doc_date_standard="1807-09-08",
        )
        index_data = document.index_data()
        # should display form of the date without tags
        assert index_data["document_date_t"] == strip_tags(document.document_date)

        # unparsable standard date shouldn't error, displays as-is
        document.doc_date_standard = "1145-46"
        index_data = document.index_data()
        assert index_data["document_date_t"] == strip_tags(document.document_date)

        # unset date should index as None/empty
        index_data = Document(id=1234).index_data()
        assert index_data["document_date_t"] is None

    def test_index_data_old_shelfmarks(self, join):
        fragment = join.fragments.first()
        old_shelfmarks = ["p. Heid. Arab. 917", "p. Heid. 917"]
        fragment.old_shelfmarks = "; ".join(old_shelfmarks)
        fragment.save()
        fragment2 = join.fragments.all()[1]
        fragment2.old_shelfmarks = "Yevr.-Arab. II 991"
        fragment2.save()

        index_data = join.index_data()
        print(index_data["fragment_old_shelfmark_ss"])
        all_old_shelfmarks = old_shelfmarks
        all_old_shelfmarks.append(fragment2.old_shelfmarks)
        assert index_data["fragment_old_shelfmark_ss"] == all_old_shelfmarks

    def test_index_data_input_date(self):
        doc = Document.objects.create()
        # when no logentry exists, should still get the year from created attr
        assert not LogEntry.objects.filter(
            object_id=doc.pk,
            content_type_id=ContentType.objects.get_for_model(doc).id,
        ).exists()
        assert doc.index_data()["input_year_i"] == doc.created.year

    def test_index_data_locale(self):
        # create a doctype with a label in hebrew and english
        dt = DocumentType.objects.create(
            display_label_he="wrong", display_label_en="right"
        )
        # in english, str should return english label
        activate("en")
        assert str(dt) == "right"
        # in hebrew, str should return hebrew label
        activate("he")
        assert str(dt) == "wrong"
        # but index data should always be in english
        doc = Document.objects.create(doctype=dt)
        assert doc.index_data()["type_s"] == "right"
        activate("en")

    def test_editions(self, document, source):
        # create multiple footnotes to test filtering and sorting

        edition = Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.EDITION
        )
        digital_edition = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=[Footnote.DIGITAL_EDITION],
        )
        translation = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.TRANSLATION,
        )

        doc_edition_pks = [doc.pk for doc in document.editions()]
        # check that only footnotes with doc relation including edition are included
        # NOTE: comparing by PK rather than using footnote equality check
        assert edition.pk in doc_edition_pks
        assert digital_edition.pk not in doc_edition_pks
        assert translation.pk not in doc_edition_pks

    def test_digital_editions(self, document, source, twoauthor_source):
        # test filter by content

        # footnote with no content
        edition = Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.EDITION
        )
        # digital edition
        edition2 = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        # footnote with different source
        edition3 = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        digital_edition_pks = [ed.pk for ed in document.digital_editions()]

        # EDITION, should not appear in digital editions
        assert edition.pk not in digital_edition_pks
        # DIGITAL_EDITION, should appear in digital editions
        assert edition2.pk in digital_edition_pks
        assert edition3.pk in digital_edition_pks
        # Edition 2 should be alphabetically first based on its source
        assert edition2.pk == digital_edition_pks[0]

    def test_editors(self, document, source, twoauthor_source):
        # footnote with no digital edition
        Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.EDITION
        )
        # No digital editions, so editors count should be 0
        assert document.editors().count() == 0

        # Digital edition with one author
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )

        # Digital edition with one author, editor should be author of source
        assert document.editors().count() == 1
        assert document.editors().first() == source.authors.first()

        # Digital edition with two authors
        Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        # Should now be three editors, since this edition's source had two authors
        assert document.editors().count() == 3
        assert twoauthor_source.authors.first().pk in [
            editor.pk for editor in document.editors().all()
        ]

    def test_digital_translations(self, document, source, twoauthor_source):
        # translation footnote
        translation = Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.TRANSLATION
        )
        # digital translation
        digital_translation = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        # footnote with different source
        digital_translation2 = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        digital_translation_pks = [ed.pk for ed in document.digital_translations()]

        # EDITION, should not appear in digital editions
        assert translation.pk not in digital_translation_pks
        # DIGITAL_EDITION, should appear in digital editions
        assert digital_translation.pk in digital_translation_pks
        assert digital_translation2.pk in digital_translation_pks
        # Translation 1 should be alphabetically first based on its source title
        assert digital_translation.pk == digital_translation_pks[0]

    def test_default_translation(self, document, source, twoauthor_source):
        book = SourceType.objects.create(type="Book")
        hebrew = SourceLanguage.objects.get(name="Hebrew")
        hebrew_source = Source.objects.create(
            title_en="Some Translations", source_type=book
        )
        hebrew_source.languages.add(hebrew)
        h = Footnote.objects.create(
            content_object=document,
            source=hebrew_source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        eng1 = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        eng2 = Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )

        current_lang = get_language()
        activate("he")
        # should choose the first translation in the user's selected language
        assert document.default_translation.pk == h.pk
        # should be ordered alphabetically, by source title
        activate("en")
        assert document.default_translation.pk == eng1.pk

        # if there are none in the selected language, should choose first of all translations
        # alphabetically, by source title
        doc2 = Document.objects.create()
        h1 = Footnote.objects.create(
            content_object=doc2,
            source=hebrew_source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        hebrew_source_2 = Source.objects.create(
            title_en="All Translations", source_type=book
        )
        hebrew_source_2.languages.add(hebrew)
        h2 = Footnote.objects.create(
            content_object=doc2,
            source=hebrew_source_2,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        assert doc2.default_translation.pk == h2.pk

        activate(current_lang)

    def test_digital_footnotes(self, document, source):
        # no digital edition or digital translation, count should be 0
        regular_translation = Footnote.objects.create(
            content_object=document, source=source, doc_relation=Footnote.TRANSLATION
        )
        assert document.digital_footnotes().count() == 0
        # digital edition, count should be 1
        digital_edition = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_EDITION,
        )
        assert document.digital_footnotes().count() == 1
        # add digital translation, count should be 2 and both should be included
        digital_translation = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DIGITAL_TRANSLATION,
        )
        assert document.digital_footnotes().count() == 2
        digital_footnote_pks = [ed.pk for ed in document.digital_footnotes()]
        assert digital_translation.pk in digital_footnote_pks
        assert digital_edition.pk in digital_footnote_pks
        assert regular_translation.pk not in digital_footnote_pks

    def test_total_to_index(self, join, document):
        assert Document.total_to_index() == 2

    def test_sources(self, document, source, twoauthor_source):
        # Create two different footnotes with the same document and source
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.EDITION,
        )
        Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.TRANSLATION,
        )
        # Create one footnote with a new source
        Footnote.objects.create(
            content_object=document,
            source=twoauthor_source,
            doc_relation=Footnote.EDITION,
        )
        assert source in document.sources()
        assert twoauthor_source in document.sources()
        assert len(document.sources()) == 2

    def test_delete(self, document):
        # create a log entry to confirm disassociation
        log_entry = LogEntry.objects.create(
            user_id=1,
            content_type_id=ContentType.objects.get_for_model(document).id,
            object_id=document.id,
            object_repr="test",
            action_flag=CHANGE,
            change_message="test",
        )
        document.delete()
        # get fresh copy of the same log entry
        fresh_log_entry = LogEntry.objects.get(pk=log_entry.pk)
        assert fresh_log_entry.object_id is None

    def test_save_set_standard_date(self, document):
        document.doc_date_original = "493"
        document.doc_date_calendar = Calendar.ANNO_MUNDI
        document.doc_date_standard = ""
        document.save()

    @patch("geniza.corpus.models.messages")
    def test_save_set_standard_date_err(self, mock_messages, document):
        # use a mock to inspect call to request
        document.request = Mock()
        # something not parsable
        document.doc_date_original = "first quarter of 493"
        document.doc_date_calendar = Calendar.ANNO_MUNDI
        document.doc_date_standard = ""
        document.save()

        mock_messages.warning.assert_called_with(
            document.request,
            "Error standardizing date: 'first quarter of' is not in list",
        )

    def test_save_unicode_cleanup(self, document):
        # Should cleanup \xa0 from description
        document.description = "Test\xa0with \xa0wrong space!"
        document.save()
        assert document.description == "Test with wrong space!"

        # Should cleanup \xa0 from language specific description fields
        doc = Document.objects.create(description_he="Wrong\xa0space \xa0 here too")
        assert doc.description_he == "Wrong space here too"

    def test_manifest_uri(self, document):
        assert document.manifest_uri.startswith(settings.ANNOTATION_MANIFEST_BASE_URL)
        assert document.manifest_uri.endswith(
            reverse("corpus-uris:document-manifest", args=[document.pk])
        )

    def test_from_manifest_uri(self, document):
        # should resolve correct manifest URI to Document object
        resolved_doc = Document.from_manifest_uri(
            reverse("corpus-uris:document-manifest", kwargs={"pk": document.pk})
        )
        assert isinstance(resolved_doc, Document)
        assert resolved_doc.pk == document.pk

        # should fail on bad URI
        with pytest.raises(Resolver404):
            Document.from_manifest_uri(f"http://bad.com/example")
        with pytest.raises(Resolver404):
            Document.from_manifest_uri(
                f"http://bad.com/example/not/{document.pk}/a/manifest/"
            )

    def test_dating_range(self, document, join):
        # document with no dates or datings should return [None, None]
        assert document.dating_range() == (None, None)

        # document with single date should return numeric format min and max
        document.doc_date_standard = "1000"
        assert document.dating_range() == (PartialDate("1000"), PartialDate("1000"))

        # document with date range should return numeric format min and max
        document.doc_date_standard = "1000/1010"
        assert document.dating_range() == (PartialDate("1000"), PartialDate("1010"))

        # document with inferred dating: should include in range
        dating = Dating.objects.create(
            document=document,
            display_date="",
            standard_date="980",
        )
        assert document.dating_range() == (PartialDate("980"), PartialDate("1010"))
        dating.standard_date = "980/1005"
        dating.save()
        assert document.dating_range() == (PartialDate("980"), PartialDate("1010"))
        dating.standard_date = "980/1020"
        dating.save()
        assert document.dating_range() == (PartialDate("980"), PartialDate("1020"))

        # document with multiple inferred datings: should include all in range
        dating2 = Dating.objects.create(
            document=document,
            display_date="",
            standard_date="960/1000",
        )
        assert document.dating_range() == (PartialDate("960"), PartialDate("1020"))

        # document with no document date: should still work using only Datings
        dating.standard_date = "980/1005"
        dating.save()
        join.dating_set.add(dating, dating2)
        assert join.dating_range() == (PartialDate("960"), PartialDate("1005"))

    def test_solr_dating_range(self, document, join):
        # no date or dating, should return none
        assert document.solr_dating_range() == None

        # standard date only, should return same as solr_date_range
        document.doc_date_standard = "1000"
        assert document.solr_dating_range() == "1000"
        assert document.solr_dating_range() == document.solr_date_range()
        document.doc_date_standard = "1000/1010"
        assert document.solr_dating_range() == "[1000 TO 1010]"
        assert document.solr_dating_range() == document.solr_date_range()

        # with a dating and standard date, should include in range
        dating = Dating.objects.create(
            document=document,
            display_date="",
            standard_date="980",
        )
        # sometimes these years will have leading 0s, solr will accept either way
        assert document.solr_dating_range() in ["[0980 TO 1010]", "[980 TO 1010]"]
        assert document.solr_dating_range() != document.solr_date_range()

        # only datings, range should be entirely from min and max among these
        dating.standard_date = "980/1005"
        dating.save()
        join.dating_set.add(dating)
        Dating.objects.create(
            document=join,
            display_date="",
            standard_date="960/990",
        )
        assert join.solr_dating_range() in ["[0960 TO 1005]", "[960 TO 1005]"]

    def test_fragments_by_provenance(self, document):
        assert not document.fragments_by_provenance
        (g, _) = Provenance.objects.get_or_create(name="Geniza")
        (ng, _) = Provenance.objects.get_or_create(name="Not Geniza")
        f1 = Fragment.objects.create(shelfmark="CUL 123", provenance_display=g)
        f2 = Fragment.objects.create(shelfmark="CUL 456", provenance_display=ng)
        TextBlock.objects.create(fragment=f1, document=document)
        assert len(document.fragments_by_provenance) > 0
        TextBlock.objects.create(fragment=f2, document=document)
        assert document.fragments_by_provenance[0].pk == f1.pk


def test_document_merge_with(document, join):
    doc_id = document.id
    doc_shelfmark = document.shelfmark
    doc_description = document.description
    join.merge_with([document], "merge test")
    # merged document should no longer be in the database
    assert not Document.objects.filter(pk=doc_id).exists()
    # merged pgpid added to primary list of old pgpids
    assert doc_id in join.old_pgpids
    # tags from merged document
    assert "bill of sale" in join.tags.names()
    assert "real estate" in join.tags.names()
    # combined descriptions
    assert doc_description in join.description
    assert "\nDescription from PGPID %s" % doc_id in join.description
    # original description from fixture should still be present
    assert "testing description" in join.description
    # no notes
    assert join.notes == ""
    # merge by script = flagged for review
    assert join.needs_review.startswith("SCRIPTMERGE")


def test_document_merge_with_no_description(document):
    doc_id = document.id
    # create a document with no description
    doc_2 = Document.objects.create()
    doc_2.merge_with([document], "test")
    # should not error; should combine descriptions
    assert "Description from PGPID %s:" % doc_id in doc_2.description
    assert document.description in doc_2.description


def test_document_merge_with_notes(document, join):
    join.notes = "original doc"
    join.needs_review = "cleanup needed"
    document.notes = "awaiting transcription"
    document.needs_review = "see join"
    doc_id = document.id
    doc_shelfmark = document.shelfmark
    join.merge_with([document], "merge test")
    assert (
        join.notes
        == "original doc\nNotes from PGPID %s:\nawaiting transcription" % doc_id
    )
    assert join.needs_review == "SCRIPTMERGE\ncleanup needed\nsee join"


def test_document_merge_with_tags(document, join):
    # same tag on both documents
    merged_doc_id = document.id
    join.tags.add("bill of sale")
    join.merge_with([document], "merge test")
    # get a fresh copy from db to test changes are saved
    updated_join = Document.objects.get(id=join.id)
    # merged pgpid added to primary list of old pgpids
    assert merged_doc_id in updated_join.old_pgpids
    # tags from merged document
    tags = updated_join.tags.names()
    assert len(tags) == 2  # tag should not exist twice
    assert "bill of sale" in tags
    assert "real estate" in tags


def test_document_merge_with_languages(document, join):
    judeo_arabic = LanguageScript.objects.create(
        language="Judaeo-Arabic", script="Hebrew"
    )
    join.languages.add(judeo_arabic)

    arabic = LanguageScript.objects.create(language="Arabic", script="Arabic")
    document.languages.add(judeo_arabic)
    document.secondary_languages.add(arabic)
    document.language_note = "with diacritics"

    join.merge_with([document], "merge test")

    assert judeo_arabic in join.languages.all()
    assert join.languages.count() == 1
    assert arabic in join.secondary_languages.all()
    assert join.language_note == document.language_note


def test_document_merge_with_textblocks(document, join):
    # join has two fragments, document only has one of those two
    assert document.fragments.count() == 1
    document.merge_with([join], "new join")
    # should have two fragments and text blocks after the merge
    assert document.fragments.count() == 2
    assert document.textblock_set.count() == 2


def test_document_merge_with_footnotes(document, join, source):
    # create some footnotes
    Footnote.objects.create(content_object=document, source=source, location="p. 3")
    # page 3 footnote is a duplicate
    Footnote.objects.create(content_object=join, source=source, location="p. 3")
    Footnote.objects.create(content_object=join, source=source, location="p. 100")

    assert document.footnotes.count() == 1
    assert join.footnotes.count() == 2
    document.merge_with([join], "combine footnotes")
    # should only have two footnotes after the merge, because two of them are equal
    assert document.footnotes.count() == 2


@pytest.mark.django_db
def test_document_merge_with_annotations(document, join, source):
    # create two footnotes, one with annotations and one without, on the same source
    Footnote.objects.create(
        content_object=document,
        source=source,
        location="p. 3",
        doc_relation=Footnote.DIGITAL_EDITION,
    )
    join_fn = Footnote.objects.create(
        content_object=join,
        source=source,
        location="p. 3",
        notes="with emendations",
        doc_relation=Footnote.DIGITAL_EDITION,
    )
    anno = Annotation.objects.create(
        footnote=join_fn, content={"body": [{"value": "foo bar baz"}]}
    )

    assert document.footnotes.count() == 1
    assert document.footnotes.first().annotation_set.count() == 0
    assert join.footnotes.count() == 1
    assert join.footnotes.first().annotation_set.count() == 1
    document.merge_with([join], "combine footnotes/annotations")
    # should still only have one footnote after merge, but now with an annotation
    assert document.footnotes.count() == 1
    assert document.footnotes.first().annotation_set.count() == 1
    # it should be the above annotation but reassigned
    anno.refresh_from_db()
    assert anno.footnote.object_id == document.pk
    # should have copied the notes over from the join fn
    assert document.footnotes.first().notes == "with emendations"


@pytest.mark.django_db
def test_document_merge_with_annotations_no_match(document, join, source):
    # create two footnotes, one digital edition and one digital translation, on the same source
    Footnote.objects.create(
        content_object=document,
        source=source,
        location="p. 3",
        doc_relation=Footnote.DIGITAL_EDITION,
    )
    join_fn = Footnote.objects.create(
        content_object=join,
        source=source,
        location="p. 3",
        notes="with emendations",
        doc_relation=Footnote.DIGITAL_TRANSLATION,
    )
    anno = Annotation.objects.create(
        footnote=join_fn, content={"body": [{"value": "foo bar baz"}]}
    )

    assert document.footnotes.count() == 1
    assert document.footnotes.first().annotation_set.count() == 0
    assert join.footnotes.count() == 1
    assert join.footnotes.first().annotation_set.count() == 1
    document.merge_with([join], "combine footnotes/annotations")
    # should now have two footnotes after merge
    assert document.footnotes.count() == 2
    # the above annotation should be reassigned
    anno.refresh_from_db()
    assert anno.footnote.object_id == document.pk


def test_document_merge_with_empty_digital_footnote(document, join, source):
    # create two digital edition footnotes on the same doc/source without annotations
    Footnote.objects.create(
        content_object=document,
        source=source,
        location="p. 3",
        doc_relation=Footnote.DIGITAL_EDITION,
    )
    new_footnote = Footnote.objects.create(
        content_object=join,
        source=source,
        location="new",
        doc_relation=Footnote.DIGITAL_EDITION,
    )

    assert document.footnotes.count() == 1
    assert document.digital_editions().count() == 1
    assert join.footnotes.count() == 1
    document.merge_with([join], "combine footnotes")
    # should have two footnotes after the merge, since location differs
    assert document.footnotes.count() == 2
    # added footnote should not be a digital edition, to prevent unique violation
    assert document.digital_editions().count() == 1

    # same should be true for a digital translation
    new_footnote.refresh_from_db()
    assert new_footnote.content_object.id == document.id
    new_footnote.doc_relation = [Footnote.DIGITAL_TRANSLATION]
    new_footnote.save()
    assert document.digital_translations().count() == 1
    other_doc = Document.objects.create()
    Footnote.objects.create(
        content_object=other_doc,
        source=source,
        location="example",
        doc_relation=Footnote.DIGITAL_TRANSLATION,
    )
    document.merge_with([other_doc], "combine translations")
    # added footnote should not be a digital translation, to prevent unique violation
    assert document.digital_translations().count() == 1


def test_document_merge_with_log_entries(document, join):
    # create some log entries
    document_contenttype = ContentType.objects.get_for_model(Document)
    # creation
    creation_date = timezone.make_aware(datetime(1991, 5, 1))
    creator = User.objects.get_or_create(username="editor")[0]
    LogEntry.objects.bulk_create(
        [
            LogEntry(
                user_id=creator.id,
                content_type_id=document_contenttype.pk,
                object_id=document.id,
                object_repr=str(document),
                change_message="first input",
                action_flag=ADDITION,
                action_time=creation_date,
            ),
            LogEntry(
                user_id=creator.id,
                content_type_id=document_contenttype.pk,
                object_id=join.id,
                object_repr=str(join),
                change_message="first input",
                action_flag=ADDITION,
                action_time=creation_date,
            ),
            LogEntry(
                user_id=creator.id,
                content_type_id=document_contenttype.pk,
                object_id=join.id,
                object_repr=str(join),
                change_message="major revision",
                action_flag=CHANGE,
                action_time=timezone.now(),
            ),
        ]
    )

    # document has two log entries from fixture
    assert document.log_entries.count() == 3
    assert join.log_entries.count() == 2
    join_pk = join.pk
    document.merge_with([join], "combine log entries", creator)
    # should have 5 log entries after the merge:
    # original 2 from fixture, 1 of the two duplicates, 1 unique,
    # and 1 documenting the merge
    assert document.log_entries.count() == 5
    # based on default sorting, most recent log entry will be first
    # - should document the merge event
    merge_log = document.log_entries.first()
    # log action with specified user
    assert creator.id == merge_log.user_id
    assert "combine log entries" in merge_log.change_message
    assert merge_log.action_flag == CHANGE
    # not flagged for review when merged by a user
    assert "SCRIPTMERGE" not in document.needs_review

    # reassociated log entry should include old pgpid
    moved_log = document.log_entries.all()[1]
    assert " [PGPID %s]" % join_pk in moved_log.change_message


def test_document_merge_with_dates(document, join):
    editor = User.objects.get_or_create(username="editor")[0]

    # clone join for additional merges
    join_clones = []
    for _ in range(4):
        join_clone = Document.objects.get(pk=join.pk)
        join_clone.pk = None
        join_clone.save()
        join_clones.append(join_clone)

    # create some datings; doesn't matter that they are identical, as cleaning
    # up post-merge dupes is a manual data cleanup task. unit test will make
    # sure that doesn't cause errors!
    dating_1 = Dating.objects.create(
        document=document,
        display_date="1000 CE",
        standard_date="1000",
        rationale=Dating.PALEOGRAPHY,
        notes="a note",
    )
    dating_2 = Dating.objects.create(
        document=join_clone,
        display_date="1000 CE",
        standard_date="1000",
        rationale=Dating.PALEOGRAPHY,
        notes="a note",
    )

    # should raise ValidationError on conflicting dates
    document.doc_date_standard = "1230-01-01"
    join.doc_date_standard = "1234-01-01"
    with pytest.raises(ValidationError):
        document.merge_with([join], "test", editor)

    # should use any existing dates if one of the merged documents has one
    join.doc_date_standard = ""
    document.merge_with([join], "test", editor)
    assert document.doc_date_standard == "1230-01-01"

    document.doc_date_standard = ""
    document.doc_date_original = ""
    document.doc_date_calendar = ""
    join_clones[0].doc_date_original = "15 Tevet 4990"
    join_clones[0].doc_date_calendar = Calendar.ANNO_MUNDI
    document.merge_with([join_clones[0]], "test", editor)
    assert document.doc_date_original == "15 Tevet 4990"
    assert document.doc_date_calendar == Calendar.ANNO_MUNDI

    # should raise error if one document's standard date conflicts with other document's
    # original date
    document.doc_date_original = ""
    document.doc_date_standard = "1230-01-01"
    join_clones[1].doc_date_original = "1 Tevet 5000"
    join_clones[1].doc_date_calendar = Calendar.ANNO_MUNDI
    with pytest.raises(ValidationError):
        document.merge_with([join_clones[1]], "test", editor)

    document.doc_date_standard = ""
    document.doc_date_original = "1 Tevet 5000"
    document.doc_date_calendar = Calendar.ANNO_MUNDI
    join_clones[1].doc_date_original = ""
    join_clones[1].doc_date_standard = "1230-01-01"
    with pytest.raises(ValidationError):
        document.merge_with([join_clones[1]], "test", editor)

    # should not raise error on identical dates
    document.doc_date_standard = "1230-01-01"
    document.doc_date_original = "15 Tevet 4990"
    document.doc_date_calendar = Calendar.ANNO_MUNDI
    join_clones[1].doc_date_standard = "1230-01-01"
    join_clones[1].doc_date_original = "15 Tevet 4990"
    join_clones[1].doc_date_calendar = Calendar.ANNO_MUNDI
    document.merge_with([join_clones[1]], "test", editor)

    # should consider identical if one doc's standardized original date = other doc's standard date
    document.doc_date_standard = "1230-01-01"
    document.doc_date_original = ""
    document.doc_date_calendar = ""
    join_clones[2].doc_date_standard = ""
    join_clones[2].doc_date_original = "15 Tevet 4990"
    join_clones[2].doc_date_calendar = Calendar.ANNO_MUNDI
    document.merge_with([join_clones[2]], "test", editor)
    assert document.doc_date_original == "15 Tevet 4990"
    assert document.doc_date_calendar == Calendar.ANNO_MUNDI

    document.doc_date_standard = ""
    join_clones[3].doc_date_standard = "1230-01-01"
    join_clones[3].doc_date_original = ""
    join_clones[3].doc_date_calendar = ""
    document.merge_with([join_clones[3]], "test", editor)
    assert document.doc_date_standard == "1230-01-01"

    # should carry over all inferred datings without error, even if they are identical
    assert document.dating_set.count() == 2
    result_pks = [dating.pk for dating in document.dating_set.all()]
    assert dating_1.pk in result_pks and dating_2.pk in result_pks


@pytest.mark.django_db
def test_document_merge_with_description_authors(document, join):
    # create some creators and add them as description authors on the documents
    marina = Creator.objects.create(last_name_en="Rustow", first_name_en="Marina")
    amel = Creator.objects.create(last_name_en="Bensalim", first_name_en="Amel")
    document.authors.add(marina)
    join.authors.add(marina, amel)
    assert document.authors.count() == 1

    # merge join into document
    document.merge_with([join], "test")
    # should be two description authors now
    assert document.authors.count() == 2
    assert document.descriptionauthorship_set.count() == 2
    # amel should be added
    assert document.authors.contains(amel)


@pytest.mark.django_db
def test_document_merge_with_related_entities(
    document, join, person, person_diacritic, person_multiname
):
    # add person-document relationships
    (mentioned, _) = PersonDocumentRelationType.objects.get_or_create(name="Mentioned")
    (author, _) = PersonDocumentRelationType.objects.get_or_create(name="Author")
    (recipient, _) = PersonDocumentRelationType.objects.get_or_create(name="Recipient")
    # same person and type, different notes
    mentioned_rel = PersonDocumentRelation.objects.create(
        document=document, person=person, type=mentioned, notes="Mentioned on line 5."
    )
    merged_mentioned_rel = PersonDocumentRelation.objects.create(
        document=join, person=person, type=mentioned, notes="Sourced from evidence."
    )
    # same person, different type
    PersonDocumentRelation.objects.create(
        document=document,
        person=person_diacritic,
        type=author,
        notes="Authored similar.",
    )
    newtype_rel = PersonDocumentRelation.objects.create(
        document=join, person=person_diacritic, type=recipient, notes="Address on top."
    )
    # different person
    newperson_rel = PersonDocumentRelation.objects.create(
        document=join,
        person=person_multiname,
        type=recipient,
        notes="Also address on top.",
    )

    assert document.persondocumentrelation_set.count() == 2

    # merge into document as primary
    join_pk = join.pk
    document.merge_with([join], "test")

    # should have added Recipient relation with person_diacritic, and relationship with person_multiname
    assert document.persondocumentrelation_set.count() == 4

    # notes should be merged on person + type matches
    old_notes = mentioned_rel.notes
    mentioned_rel.refresh_from_db()
    assert (
        mentioned_rel.notes
        == f"{old_notes}\nNotes from PGPID {join_pk}: {merged_mentioned_rel.notes}"
    )

    # duplicate relation should be cascade-deleted
    assert not PersonDocumentRelation.objects.filter(
        pk=merged_mentioned_rel.pk
    ).exists()

    # otherwise should just reassign relationships to primary document
    newtype_rel.refresh_from_db()
    assert newtype_rel.document.pk == document.pk
    newperson_rel.refresh_from_db()
    assert newperson_rel.document.pk == document.pk

    # ensure basic merge functionality works for places and events too
    # (uses the same logic as people so no need to test in depth)
    doc3 = Document.objects.create()
    fustat = Place.objects.create()
    qasr = Place.objects.create()
    pdr_type = DocumentPlaceRelationType.objects.create()
    DocumentPlaceRelation.objects.create(document=document, place=fustat, type=pdr_type)
    DocumentPlaceRelation.objects.create(document=doc3, place=fustat, type=pdr_type)
    DocumentPlaceRelation.objects.create(document=doc3, place=qasr, type=pdr_type)
    assert document.documentplacerelation_set.count() == 1
    document.merge_with([doc3], "test")
    assert document.documentplacerelation_set.count() == 2

    doc4 = Document.objects.create()
    publication = Event.objects.create()
    founding = Event.objects.create()
    DocumentEventRelation.objects.create(document=document, event=publication)
    DocumentEventRelation.objects.create(document=doc4, event=founding)
    assert document.documenteventrelation_set.count() == 1
    document.merge_with([doc4], "test")
    assert document.documenteventrelation_set.count() == 2


def test_document_get_by_any_pgpid(document):
    # get by current pk
    assert Document.objects.get_by_any_pgpid(document.pk) == document

    # add old ids
    document.old_pgpids = [345, 678]
    document.save()

    assert Document.objects.get_by_any_pgpid(345) == document
    assert Document.objects.get_by_any_pgpid(678) == document

    with pytest.raises(Document.DoesNotExist):
        Document.objects.get_by_any_pgpid(1234)


@pytest.mark.django_db
class TestTextBlock:
    def test_str(self):
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        block = TextBlock.objects.create(
            document=doc, fragment=frag, selected_images=[0]
        )
        assert str(block) == "%s recto" % frag.shelfmark

        # with labeled region
        block.region = "a"
        block.save()
        assert str(block) == "%s recto a" % frag.shelfmark

        # with uncertainty label
        block2 = TextBlock.objects.create(
            document=doc, fragment=frag, selected_images=[0], certain=False
        )
        assert str(block2) == "%s recto (?)" % frag.shelfmark

    def test_thumbnail(self):
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        block = TextBlock.objects.create(
            document=doc, fragment=frag, selected_images=[0]
        )
        with patch.object(frag, "iiif_thumbnails") as mock_frag_thumbnails:
            assert block.thumbnail() == mock_frag_thumbnails.return_value

    def test_side(self):
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        no_side = TextBlock.objects.create(
            document=doc, fragment=frag, selected_images=[]
        )
        assert not no_side.side
        recto_side = TextBlock.objects.create(
            document=doc, fragment=frag, selected_images=[0]
        )
        assert recto_side.side == "recto"
        verso_side = TextBlock.objects.create(
            document=doc, fragment=frag, selected_images=[1]
        )
        assert verso_side.side == "verso"
        both_sides = TextBlock.objects.create(
            document=doc, fragment=frag, selected_images=[0, 1]
        )
        assert both_sides.side == "recto and verso"


@pytest.mark.django_db
def test_items_to_index(document, footnote):
    """Test that prefetching is properly configured."""
    # Because of lazy loading, querysets must be executed to test prefetches.
    # Footnote fixture must be included to check source/creator prefetching.
    docs = Document.items_to_index()
    assert docs
    assert isinstance(docs, MultilingualQuerySet)


def test_fragment_historic_shelfmarks(document, join, fragment, multifragment):
    fragment.old_shelfmarks = "ULC Add. 2586"
    fragment.save()
    assert document.fragment_historical_shelfmarks == fragment.old_shelfmarks
    assert join.fragment_historical_shelfmarks == fragment.old_shelfmarks
    multifragment.old_shelfmarks = "T-S Misc.29.6"
    multifragment.save()
    hist_string = join.fragment_historical_shelfmarks
    assert fragment.old_shelfmarks in hist_string
    assert multifragment.old_shelfmarks in hist_string


@pytest.mark.django_db
class TestDocumentEventRelation:
    def test_str(self, document):
        event = Event.objects.create(name="Founding of the Ben Ezra Synagogue")
        relation = DocumentEventRelation.objects.create(document=document, event=event)
        assert str(relation) == f"Document-Event relation: {document} and {event}"
