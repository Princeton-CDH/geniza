from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
from attrdict import AttrDict
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
from djiffy.models import Canvas, IIIFException, IIIFImage, Manifest
from modeltranslation.manager import MultilingualQuerySet
from piffle.presentation import IIIFException as piffle_IIIFException

from geniza.annotations.models import Annotation
from geniza.corpus.dates import Calendar
from geniza.corpus.models import (
    Collection,
    Document,
    DocumentType,
    Fragment,
    LanguageScript,
    TextBlock,
)
from geniza.footnotes.models import Footnote


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
        # test with recto side selected: should add class to recto img, but not verso img
        thumbnails_recto_selected = frag.iiif_thumbnails(selected=[0])
        assert 'title="recto" class="selected"' in thumbnails_recto_selected
        assert 'title="verso" class="selected"' not in thumbnails_recto_selected

        frag.iiif_url = "http://example.co/iiif/ts-1"
        # return simplified part of the manifest we need for this
        mockiifpres.from_url.return_value = AttrDict(
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

        # test with verso side selected: should add class to 1v img, but not 1r img
        thumbnails_verso_selected = frag.iiif_thumbnails(selected=[1])
        assert 'title="1v" class="selected"' in thumbnails_verso_selected
        assert 'title="1r" class="selected"' not in thumbnails_verso_selected

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
            # should raise the exception
            with self.assertRaises(IIIFException):
                # should log at level WARN
                with self.assertLogs(level="WARN"):
                    frag.iiif_images()

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
    def test_provenance(self, mock_manifestimporter):
        # fragment with no manifest
        frag = Fragment(shelfmark="TS 1")
        assert not frag.provenance

        # fragment with a locally cached manifest
        frag = Fragment(shelfmark="TS 2")
        frag.iiif_url = "http://example.io/manifests/2"
        # manifest with an attribution
        frag.manifest = Manifest.objects.create(
            uri=frag.iiif_url, short_id="m", metadata={"Provenance": ["From a place"]}
        )
        mock_manifestimporter.return_value.import_paths.return_value = [frag.manifest]
        frag.save()
        assert frag.provenance == "From a place"

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
        mock_manifestimporter.return_value.import_paths.side_effect = (
            piffle_IIIFException
        )
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

            # call with image_order_override present, reversed order
            doc.image_order_override = ["canvas2", "canvas1"]
            images = doc.iiif_images()
            # img2 should come first now
            assert list(images.keys()) == ["canvas2", "canvas1"]

    def test_admin_thumbnails(self):
        # Create a document and fragment and a TextBlock to associate them
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        TextBlock.objects.create(document=doc, fragment=frag, selected_images=[0])
        # Mock two IIIF images, mock their size functions
        img1 = Mock()
        img1.size.return_value = "/img1.jpg"
        img2 = Mock()
        img2.size.return_value = "/img2.jpg"
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

    def test_has_image(self, document, fragment):
        # doc with fragment with IIIF url has image
        assert document.has_image()

        # remove IIIF url from fragment; doc should no longer have image
        fragment.iiif_url = ""
        fragment.save()
        assert not document.has_image()

    def test_index_data(self, document):
        index_data = document.index_data()
        assert index_data["id"] == document.index_id()
        assert index_data["item_type_s"] == "document"
        assert index_data["pgpid_i"] == document.pk
        assert index_data["type_s"] == str(document.doctype)
        assert index_data["description_t"] == document.description
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
            assert index_data["has_image_b"] is True

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
            content={
                "body": [{"value": "transcription lines"}],
                "target": {"source": {"partOf": {"id": document.manifest_uri}}},
                "dc:source": source.uri,
            }
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
        assert index_data["num_translations_i"] == 2
        assert index_data["scholarship_count_i"] == 3  # unique sources
        assert index_data["transcription_ht"] == ["transcription lines"]

        for note in [edition, edition2, translation]:
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

    def test_manifest_uri(self, document):
        assert document.manifest_uri.startswith(settings.ANNOTATION_MANIFEST_BASE_URL)
        assert document.manifest_uri.endswith(
            reverse("corpus:document-manifest", args=[document.pk])
        )

    def test_id_from_manifest_uri(self, document):
        # should resolve correct manifest URI to Document id
        resolved_doc_id = Document.id_from_manifest_uri(
            reverse("corpus:document-manifest", kwargs={"pk": document.pk})
        )
        assert isinstance(resolved_doc_id, int)
        assert resolved_doc_id == document.pk

        # should fail on resolvable non-manifest URI
        with pytest.raises(Resolver404):
            Document.id_from_manifest_uri(f"http://bad.com/documents/3/")

    def test_from_manifest_uri(self, document):
        # should resolve correct manifest URI to Document object
        resolved_doc = Document.from_manifest_uri(
            reverse("corpus:document-manifest", kwargs={"pk": document.pk})
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


def test_document_get_by_any_pgpid(document):
    # get by current pk
    assert Document.get_by_any_pgpid(document.pk) == document

    # add old ids
    document.old_pgpids = [345, 678]
    document.save()

    assert Document.get_by_any_pgpid(345) == document
    assert Document.get_by_any_pgpid(678) == document

    assert not Document.get_by_any_pgpid(1234)


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
    assert type(docs) is MultilingualQuerySet
