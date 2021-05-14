from unittest.mock import patch

from attrdict import AttrDict
from django.db import IntegrityError
from django.utils.safestring import SafeString
from django.urls import reverse
import pytest

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


class TestFragment:
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
        # no iiif
        frag = Fragment(shelfmark="TS 1")
        assert frag.iiif_thumbnails() == ""

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
                                            "id": "http://example.co/iiif/ts-1/00001",
                                        }
                                    }
                                ],
                                "label": "1r",
                            },
                            {
                                "images": [
                                    {
                                        "resource": {
                                            "id": "http://example.co/iiif/ts-1/00002",
                                        }
                                    }
                                ],
                                "label": "1v",
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

    @pytest.mark.django_db
    def test_save(self):
        frag = Fragment(shelfmark="TS 1")
        frag.save()
        frag.shelfmark = "TS 2"
        frag.save()
        assert frag.old_shelfmarks == "TS 1"

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


class TestDocumentType:
    def test_str(self):
        doctype = DocumentType(name="Legal")
        assert str(doctype) == doctype.name


@pytest.mark.django_db
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

    def test_str(self):
        frag = Fragment.objects.create(shelfmark="Or.1081 2.25")
        doc = Document.objects.create()
        doc.fragments.add(frag)
        assert doc.shelfmark in str(doc) and str(doc.id) in str(doc)

        unsaved_doc = Document()
        assert str(unsaved_doc) == "?? (PGPID ??)"

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

    def test_tag_list(self):
        doc = Document.objects.create()
        doc.tags.add("marriage", "women")
        tag_list = doc.tag_list()
        # tag order is not reliable, so just check all the pieces
        assert "women" in tag_list
        assert "marriage" in tag_list
        assert ", " in tag_list

    def test_is_public(self):
        doc = Document.objects.create()
        assert doc.is_public()
        doc.status = "S"
        assert not doc.is_public()

    def test_get_absolute_url(self):
        doc = Document.objects.create(id=1)
        assert doc.get_absolute_url() == "/documents/1/"

    def test_iiif_urls(self):
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

    def test_title(self):
        doc = Document.objects.create()
        assert doc.title == "Unknown: ??"
        legal = DocumentType.objects.get_or_create(name="Legal")[0]
        doc.doctype = legal
        doc.save()
        assert doc.title == "Legal: ??"
        frag = Fragment.objects.create(shelfmark="s1")
        TextBlock.objects.create(document=doc, fragment=frag, order=1)
        assert doc.title == "Legal: s1"

    def test_shelfmark_display(self):
        # T-S 8J22.21 + T-S NS J193
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        doc = Document.objects.create()
        TextBlock.objects.create(document=doc, fragment=frag, order=1)
        # single fragment
        assert doc.shelfmark_display == frag.shelfmark

        # add a second text block with the same fragment
        TextBlock.objects.create(document=doc, fragment=frag)
        # shelfmark should not repeat
        assert doc.shelfmark_display == frag.shelfmark

        frag2 = Fragment.objects.create(shelfmark="T-S NS J193")
        TextBlock.objects.create(document=doc, fragment=frag2, order=2)
        # multiple fragments: show first shelfmark + join indicator
        assert doc.shelfmark_display == "%s + …" % frag.shelfmark

        # ensure shelfmark honors order
        doc2 = Document.objects.create()
        TextBlock.objects.create(document=doc2, fragment=frag2, order=1)
        TextBlock.objects.create(document=doc2, fragment=frag, order=2)
        assert doc2.shelfmark_display == "%s + …" % frag2.shelfmark

        # if no certain shelfmarks, don't return anything
        doc3 = Document.objects.create()
        frag3 = Fragment.objects.create(shelfmark="T-S NS J195")
        TextBlock.objects.create(document=doc3, fragment=frag3, certain=False, order=1)
        assert doc3.shelfmark_display == None

        # use only the first certain shelfmark
        TextBlock.objects.create(document=doc3, fragment=frag2, order=2)
        assert doc3.shelfmark_display == frag2.shelfmark

    def test_has_transcription(self, document, source):
        # doc with no footnotes doesn't have transcription
        assert not document.has_transcription()

        # doc with empty footnote doesn't have transcription
        fn = Footnote.objects.create(content_object=document, source=source)
        assert not document.has_transcription()

        # doc with footnote with content does have a transcription
        fn.content = "The transcription"
        fn.save()
        assert document.has_transcription

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
        assert index_data["notes_t"] == document.notes
        assert index_data["needs_review_t"] == document.needs_review
        for frag in document.fragments.all():
            assert frag.shelfmark in index_data["shelfmark_t"]
        for tag in document.tags.all():
            assert tag.name in index_data["tags_t"]
        assert index_data["status_s"] == "Public"

        # suppressed documents are still indexed,
        # since they need to be searchable in admin
        document.status = Document.SUPPRESSED
        index_data = document.index_data()
        assert index_data["id"] == document.index_id()
        assert "item_type_s" in index_data
        assert index_data["status_s"] == "Suppressed"


@pytest.mark.django_db
class TestTextBlock:
    def test_str(self):
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        block = TextBlock.objects.create(document=doc, fragment=frag, side="r")
        assert str(block) == "%s recto" % frag.shelfmark

        # with labeled region
        block.region = "a"
        block.save()
        assert str(block) == "%s recto a" % frag.shelfmark

        # with uncertainty label
        block2 = TextBlock.objects.create(
            document=doc, fragment=frag, side="r", certain=False
        )
        assert str(block2) == "%s recto (?)" % frag.shelfmark

    def test_thumbnail(self):
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
        block = TextBlock.objects.create(document=doc, fragment=frag, side="r")
        with patch.object(frag, "iiif_thumbnails") as mock_frag_thumbnails:
            assert block.thumbnail() == mock_frag_thumbnails.return_value
