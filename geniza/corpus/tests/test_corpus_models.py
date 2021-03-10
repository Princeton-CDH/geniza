from unittest.mock import patch

from attrdict import AttrDict
from django.db import IntegrityError
from django.utils.safestring import SafeString
import pytest

from geniza.corpus.models import Collection, Document, DocumentType, \
    Fragment, LanguageScript, TextBlock


class TestCollection:

    def test_str(self):
        # library only
        lib = Collection(library='British Library', abbrev='BL')
        assert str(lib) == lib.library

        # library + collection
        cul_ts = Collection(
            library='Cambridge UL', name='Taylor-Schechter',
            lib_abbrev='CUL', abbrev='T-S')
        assert str(cul_ts) == '%s, %s' % (cul_ts.name, cul_ts.library)

        # collection only
        chapira = Collection(name='Chapira')
        assert str(chapira) == 'Chapira'

    def test_natural_key(self):
        lib = Collection(library='British Library', abbrev='BL')
        assert lib.natural_key() == ('', 'British Library')

        # library + collection
        cul_ts = Collection(
            library='Cambridge UL', name='Taylor-Schechter',
            lib_abbrev='CUL', abbrev='T-S')
        assert cul_ts.natural_key() == ('Taylor-Schechter', 'Cambridge UL')

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        lib = Collection.objects.create(library='British Library', abbrev='BL')
        assert Collection.objects.get_by_natural_key('', 'British Library') \
            == lib

        cul_ts = Collection.objects.create(
            library='Cambridge UL', name='Taylor-Schechter',
            lib_abbrev='CUL', abbrev='T-S')
        assert Collection.objects.get_by_natural_key(
            'Taylor-Schechter', 'Cambridge UL') == cul_ts

    @pytest.mark.django_db
    def test_library_or_name_required(self):
        # library only
        Collection.objects.create(library='British Library')
        # collection only
        Collection.objects.create(name='Chapira')
        # library + collection
        Collection.objects.create(library='Cambridge UL', name='Taylor-Schechter')

        # one of library or name is required
        with pytest.raises(IntegrityError):
            Collection.objects.create(lib_abbrev='BL')


class TestLanguageScripts:

    def test_str(self):
        # test display_name overwrite
        lang = LanguageScript(display_name='Judaeo-Arabic',
                              language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == lang.display_name

        # test proper string formatting
        lang = LanguageScript(language='Judaeo-Arabic', script='Hebrew')
        assert str(lang) == 'Judaeo-Arabic (Hebrew script)'

    def test_natural_key(self):
        lang = LanguageScript(language='Judaeo-Arabic', script='Hebrew')
        assert lang.natural_key() == (lang.language, lang.script)

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        lang = LanguageScript.objects.create(language='Judaeo-Arabic',
                                             script='Hebrew')
        assert LanguageScript.objects \
            .get_by_natural_key(lang.language, lang.script) == lang


class TestFragment:

    def test_str(self):
        frag = Fragment(shelfmark='TS 1')
        assert str(frag) == frag.shelfmark

    def test_is_multifragment(self):
        frag = Fragment(shelfmark='TS 1')
        assert not frag.is_multifragment()

        frag.multifragment = 'a'
        assert frag.is_multifragment()

    def test_natural_key(self):
        frag = Fragment(shelfmark='TS 1')
        assert frag.natural_key() == (frag.shelfmark, )

    @pytest.mark.django_db
    def test_get_by_natural_key(self):
        frag = Fragment.objects.create(shelfmark='TS 1')
        assert Fragment.objects.get_by_natural_key(frag.shelfmark) == frag

    @patch('geniza.corpus.models.IIIFPresentation')
    def test_iiif_thumbnails(self, mockiifpres):
        # no iiif
        frag = Fragment(shelfmark='TS 1')
        assert frag.iiif_thumbnails() == ''

        frag.iiif_url = 'http://example.co/iiif/ts-1'
        # return simplified part of the manifest we need for this
        mockiifpres.from_url.return_value = AttrDict({
            "sequences": [{
                "canvases": [
                    {
                        "images": [{
                            "resource": {
                                "id": "http://example.co/iiif/ts-1/00001",
                            }
                        }],
                        'label': '1r'
                    },
                    {
                        "images": [{
                            "resource": {
                                "id": "http://example.co/iiif/ts-1/00002",
                            }
                        }],
                        'label': '1v'
                    }
                ]
            }]
        })

        thumbnails = frag.iiif_thumbnails()
        assert '<img src="http://example.co/iiif/ts-1/00001/full/,200/0/default.jpg" loading="lazy"' \
            in thumbnails
        assert 'title="1r"' in thumbnails
        assert 'title="1v"' in thumbnails
        assert isinstance(thumbnails, SafeString)


class TestDocumentType:

    def test_str(self):
        doctype = DocumentType(name='Legal')
        assert str(doctype) == doctype.name


@pytest.mark.django_db
class TestDocument:

    def test_shelfmark(self):
        # T-S 8J22.21 + T-S NS J193
        frag = Fragment.objects.create(shelfmark='T-S 8J22.21')
        doc = Document.objects.create()
        doc.fragments.add(frag)
        # single fragment
        assert doc.shelfmark == frag.shelfmark

        frag2 = Fragment.objects.create(shelfmark='T-S NS J193')
        doc.fragments.add(frag2)
        # multiple fragments: combine shelfmarks
        assert doc.shelfmark == '%s + %s' % \
            (frag.shelfmark, frag2.shelfmark)

    def test_str(self):
        frag = Fragment.objects.create(shelfmark='Or.1081 2.25')
        doc = Document.objects.create()
        doc.fragments.add(frag)
        assert doc.shelfmark in str(doc) and str(doc.id) in str(doc)

        unsaved_doc = Document()
        assert str(unsaved_doc) == '?? (PGPID ??)'

    def test_collection(self):
        # T-S 8J22.21 + T-S NS J193
        frag = Fragment.objects.create(shelfmark='T-S 8J22.21')
        doc = Document.objects.create()
        doc.fragments.add(frag)
        # single fragment with no collection
        assert doc.collection == ''

        cul = Collection.objects.create(library='Cambridge', abbrev='CUL')
        frag.collection = cul
        frag.save()
        assert doc.collection == cul.abbrev

        # second fragment in the same collection
        frag2 = Fragment.objects.create(shelfmark='T-S NS J193',
                                        collection=cul)
        doc.fragments.add(frag2)
        assert doc.collection == cul.abbrev

        # second fragment in a different collection
        jts = Collection.objects.create(library='Jewish Theological',
                                        abbrev='JTS')
        frag2.collection = jts
        frag2.save()
        assert doc.collection == 'CUL, JTS'

    def test_is_textblock(self):
        doc = Document.objects.create()
        # no fragments
        assert not doc.is_textblock()

        # fragment but not text block
        frag = Fragment.objects.create(shelfmark='T-S 8J22.21')
        block = TextBlock.objects.create(document=doc, fragment=frag)
        assert not doc.is_textblock()

        block.extent_label = 'a'
        block.save()
        assert doc.is_textblock()

    def test_all_languages(self):
        doc = Document.objects.create()
        lang = LanguageScript.objects \
            .create(language='Judaeo-Arabic', script='Hebrew')
        doc.languages.add(lang)
        # single language
        assert doc.all_languages() == str(lang)

        arabic = LanguageScript.objects.create(language='Arabic',
                                               script='Arabic')
        doc.languages.add(arabic)
        assert doc.all_languages() == '%s,%s' % (arabic, lang)

    def test_tag_list(self):
        doc = Document.objects.create()
        doc.tags.add('marriage', 'women')
        tag_list = doc.tag_list()
        # tag order is not reliable, so just check all the pieces
        assert 'women' in tag_list
        assert 'marriage' in tag_list
        assert ', ' in tag_list


@pytest.mark.django_db
class TestTextBlock:

    def test_str(self):
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark='T-S 8J22.21')
        block = TextBlock.objects.create(document=doc, fragment=frag,
                                         side='r')
        assert str(block) == '%s recto' % frag.shelfmark

        # with labeled extent
        block.extent_label = 'a'
        block.save()
        assert str(block) == '%s recto a' % frag.shelfmark

    def test_thumbnail(self):
        doc = Document.objects.create()
        frag = Fragment.objects.create(shelfmark='T-S 8J22.21')
        block = TextBlock.objects.create(document=doc, fragment=frag,
                                         side='r')
        with patch.object(frag, 'iiif_thumbnails') as mock_frag_thumbnails:
            assert block.thumbnail() == mock_frag_thumbnails.return_value
