from io import StringIO
from unittest.mock import patch, DEFAULT

from attrdict import AttrMap
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
import pytest
import requests

from geniza.corpus.management.commands import import_data
from geniza.corpus.models import Collection, Document, DocumentType, \
    Fragment, LanguageScript


@pytest.mark.django_db
@override_settings()
def test_setup_config_error():
    del settings.DATA_IMPORT_URLS
    with pytest.raises(CommandError):
        import_data.Command().setup()


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})
def test_setup():
    import_data_cmd = import_data.Command()
    import_data_cmd.setup()
    # script user should be set
    assert import_data_cmd.script_user
    assert import_data_cmd.script_user.username == settings.SCRIPT_USERNAME


@override_settings(DATA_IMPORT_URLS={})
def test_get_csv_notconfigured():
    with pytest.raises(CommandError) as err:
        # NOTE: must consume the generator to make sure code executes
        list(import_data.Command().get_csv('libraries'))
    assert 'not configured' in str(err)


@override_settings(DATA_IMPORT_URLS={'libraries': 'http://example.co/lib.csv'})
@patch('geniza.corpus.management.commands.import_data.requests')
def test_get_csv_error(mockrequests):
    # simulate 404 result
    mockrequests.codes = requests.codes
    mockrequests.get.return_value.status_code = 404
    with pytest.raises(CommandError) as err:
        list(import_data.Command().get_csv('libraries'))

    mockrequests.get.assert_called_with(settings.DATA_IMPORT_URLS['libraries'],
                                        stream=True)
    assert 'Error accessing' in str(err)


@override_settings(DATA_IMPORT_URLS={'libraries': 'http://example.co/lib.csv'})
def test_get_csv_success():
    # simulate 200 result
    with patch.object(requests, 'get') as mockget:
        mockget.return_value.status_code = 200
        mockget.return_value.iter_lines.return_value = iter([
            b'Library,Abbreviation',
            b'British Library,BL',
            b'Bodleian Library,BODL'
        ])
        data = list(import_data.Command().get_csv('libraries'))
        assert data[0].library == 'British Library'


@override_settings(DATA_IMPORT_URLS={'metadata': 'http://example.co/mdata.csv'})
def test_get_csv_maximum():
    # simulate 200 result
    with patch.object(requests, 'get') as mockget:
        mockget.return_value.status_code = 200
        mockget.return_value.iter_lines.return_value = iter([
            b'Library,Abbreviation',
            b'British Library,BL',
            b'Bodleian Library,BODL',
            b'Third,3rd'
        ])
        import_data_cmd = import_data.Command()
        import_data_cmd.max_documents = 2
        data = list(import_data_cmd.get_csv('metadata'))
        assert len(data) == 2


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={'libraries': 'lib.csv'})  # must be set for command setup
@patch('geniza.corpus.management.commands.import_data.requests')
def test_import_collections(mockrequests):
    # create test collection to confirm it is removed
    Collection.objects.create(library='Junk Library', abbrev='JunkL')

    import_data_cmd = import_data.Command()
    import_data_cmd.setup()
    mockrequests.codes = requests.codes   # patch in actual response codes
    mockrequests.get.return_value.status_code = 200
    mockrequests.get.return_value.iter_lines.return_value = iter([
        b'Current List of Libraries,Library,Library abbreviation,Location (current),Collection (if different from library),Collection abbreviation',
        b'BL,British Library,BL,,,',
        b'BODL,Bodleian Library,BODL,,,',
        b'BODL,,Incomplete,,,',
        b'CHAPIRA,,,,Chapira,',
        b'RNL,National Library of Russia,RNL,St. Petersburg,Firkovitch,'
    ])
    import_data_cmd.import_collections()
    assert Collection.objects.count() == 4
    bl = Collection.objects.get(lib_abbrev='BL')
    assert bl.library == 'British Library'
    assert not bl.name
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 4
    # check that location and collection are populated when present
    rnl = Collection.objects.get(lib_abbrev='RNL')
    assert rnl.location == 'St. Petersburg'
    assert rnl.name == 'Firkovitch'

    # check collection-only entry
    chapira = Collection.objects.get(name='Chapira')
    for unset_field in ['library', 'location', 'lib_abbrev', 'abbrev']:
        assert not getattr(chapira, unset_field)

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        import_data_cmd.logentry_message

    # existing library records removed
    assert not Collection.objects.filter(library='Junk Library').exists()


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={'languages': 'mylangs.csv'})  # must be set for command setup
@patch('geniza.corpus.management.commands.import_data.requests')
def test_import_languages(mockrequests):
    LanguageScript.objects.create(script='Wingdings', language='English')

    import_data_cmd = import_data.Command()
    import_data_cmd.setup()
    mockrequests.codes = requests.codes   # patch in actual response codes
    mockrequests.get.return_value.status_code = 200
    mockrequests.get.return_value.iter_lines.return_value = iter([
        b'Language,Script,Vocalization,Number,',
        b'Polish,Latin,,,',
        b'Portuguese,Latin,,,',
        b',,,,note'  # should ignore empty row
    ])
    import_data_cmd.import_languages()
    mockrequests.get.assert_called_with('mylangs.csv', stream=True)
    assert LanguageScript.objects.count() == 2
    assert LanguageScript.objects.get(language='Polish').script == 'Latin'
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        import_data_cmd.logentry_message

    # existing LanguageScript records removed
    assert not LanguageScript.objects.filter(script='Wingdings').exists()


@pytest.mark.django_db
def test_get_doctype():
    import_data_cmd = import_data.Command()
    letter = import_data_cmd.get_doctype('Letter')
    assert isinstance(letter, DocumentType)
    assert letter.name == 'Letter'
    assert import_data_cmd.doctype_lookup['Letter'] == letter


def test_get_iiif_url():
    import_data_cmd = import_data.Command()

    # use attrdict to simulate namedtuple used for csv data
    data = AttrMap({
        # cudl links can be converted to iiif
        'image_link': 'https://cudl.lib.cam.ac.uk/view/MS-ADD-02586'
    })
    assert import_data_cmd.get_iiif_url(data) == \
        'https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586'

    # some cudl urls have trailing /#
    data.image_link = 'https://cudl.lib.cam.ac.uk/view/MS-ADD-03430/1'
    assert import_data_cmd.get_iiif_url(data) == \
        'https://cudl.lib.cam.ac.uk/iiif/MS-ADD-03430'

    # cudl search link cannot be converted
    data.image_link = 'https://cudl.lib.cam.ac.uk/search?fileID=&keyword=T-s%2013J33'
    assert import_data_cmd.get_iiif_url(data) == ''


def test_get_collection():
    import_data_cmd = import_data.Command()
    # simulate collection lookup already populated
    bl = Collection(library='British Library')
    cul_or = Collection(library='Cambridge', abbrev='Or.')
    import_data_cmd.collection_lookup = {
        'BL': bl,
        'CUL_Or.': cul_or
    }
    # use attrdict to simulate namedtuple used for csv data
    # - simple library lookup
    data = AttrMap({
        'library': 'BL'
    })
    assert import_data_cmd.get_collection(data) == bl
    # - library + collection lookup
    data = AttrMap({
        'library': 'CUL',
        'shelfmark': 'CUL Or. 10G5.3'
    })
    assert import_data_cmd.get_collection(data) == cul_or

    # - library + collection lookup mismatch
    data.shelfmark = 'ENA 1234.5'
    assert import_data_cmd.get_collection(data) is None


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})
def test_get_fragment():
    # get existing fragment if there is one
    myfrag = Fragment.objects.create(shelfmark='CUL Add.3350')
    import_data_cmd = import_data.Command()
    import_data_cmd.setup()
    data = AttrMap({
        'shelfmark': 'CUL Add.3350'
    })
    assert import_data_cmd.get_fragment(data) == myfrag

    # create new fragment if there isn't
    data = AttrMap({
        'shelfmark': 'CUL Add.3430',
        'shelfmark_historic': '',
        'multifragment': '',
        'library': 'CUL',
        'image_link': 'https://cudl.lib.cam.ac.uk/view/MS-ADD-03430/1'
    })
    # simulate library lookup already populated
    import_data_cmd.library_lookup = {
        'CUL': Collection.objects.create(library='CUL')
    }
    newfrag = import_data_cmd.get_fragment(data)
    assert newfrag.shelfmark == data.shelfmark
    assert newfrag.url == data.image_link
    assert newfrag.iiif_url   # should be set
    assert not newfrag.old_shelfmarks
    assert not newfrag.is_multifragment
    # log entry should be created
    fragment_ctype = ContentType.objects.get_for_model(Fragment)
    assert LogEntry.objects.get(action_flag=ADDITION, object_id=newfrag.pk,
                                content_type_id=fragment_ctype.pk)

    # test historic & multifrag values
    data.shelfmark = 'something else 123'
    data.shelfmark_historic = 'old id 1, old id 2'
    data.multifragment = 'a'
    newfrag = import_data_cmd.get_fragment(data)
    assert newfrag.old_shelfmarks == data.shelfmark_historic
    assert newfrag.is_multifragment


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={'metadata': 'pgp_meta.csv'})
@patch('geniza.corpus.management.commands.import_data.requests')
def test_import_documents(mockrequests):
    # create test fragments & documents to confirm they are removed
    Fragment.objects.create(shelfmark='foo 1')
    Document.objects.create(notes='test doc')

    import_data_cmd = import_data.Command()
    import_data_cmd.stdout = StringIO()
    # simulate collection lookup already populated
    import_data_cmd.collection_lookup = {
        'CUL_Add.': Collection.objects.create(library='CUL', abbrev='Add.')
    }
    import_data_cmd.setup()
    mockrequests.codes = requests.codes   # patch in actual response codes
    mockrequests.get.return_value.status_code = 200
    mockrequests.get.return_value.iter_lines.return_value = iter([
        b'PGPID,Library,Shelfmark - Current,Recto or verso (optional),Type,Tags,Description,Input by (optional),Date entered (optional),Language (optional),Shelfmark - Historic,Multifragment (optional),Link to image,Text-block (optional),Joins',
        b'2291,CUL,CUL Add.3358,verso,Legal,#lease #synagogue #11th c,"Lease of a ruin belonging to the Great Synagogue of Ramle, ca. 1038.",Sarah Nisenson,2017,,,middle,,a,',
        b'2292,CUL,CUL Add.3359,verso,Legal,#lease #synagogue #11th c,"Lease of a ruin belonging to the Great Synagogue of Ramle, ca. 1038.",Sarah Nisenson,2017,,,,,,CUL Add.3358 + CUL Add.3359 + NA',
        b'2293,CUL,CUL Add.3360,,Legal;Letter,,recto: one thing; verso: another,,,,,,,,'
    ])
    import_data_cmd.import_documents()
    assert Document.objects.count() == 2
    assert Fragment.objects.count() == 3
    doc = Document.objects.get(id=2291)
    assert doc.fragments.count() == 1
    assert doc.shelfmark == 'CUL Add.3358'
    assert doc.fragments.first().collection.library == 'CUL'
    assert doc.doctype.name == 'Legal'
    assert doc.textblock_set.count()
    # check text block side, extent label, multifragment
    textblock = doc.textblock_set.first()
    assert textblock.side == 'v'
    assert textblock.extent_label == 'a'
    assert textblock.multifragment == 'middle'

    assert doc.description == \
        'Lease of a ruin belonging to the Great Synagogue of Ramle, ca. 1038.'
    assert doc.old_input_by == 'Sarah Nisenson'
    assert doc.old_input_date == '2017'
    tags = set([t.name for t in doc.tags.all()])
    assert set(['lease', 'synagogue', '11th c']) == tags
    # log entry should be created
    document_ctype = ContentType.objects.get_for_model(Document)
    assert LogEntry.objects.get(action_flag=ADDITION, object_id=doc.pk,
                                content_type_id=document_ctype.pk)

    doc2 = Document.objects.get(id=2292)
    assert doc2.fragments.count() == 3
    assert Fragment.objects.get(shelfmark='NA')

    # check script summary output
    output = import_data_cmd.stdout.getvalue()
    assert 'Imported 2 documents' in output
    assert '1 with joins' in output
    assert 'skipped 1' in output
    assert LogEntry.objects.get(action_flag=ADDITION, object_id=doc2.pk,
                                content_type_id=document_ctype.pk)


@pytest.mark.django_db
def test_add_document_language():
    import_data_cmd = import_data.Command()
    import_data_cmd.stdout = StringIO()

    # simulate language lookup already populated
    arabic = LanguageScript.objects.create(language='Arabic', script='Arabic')
    hebrew = LanguageScript.objects.create(language='Hebrew', script='Hebrew')
    import_data_cmd.language_lookup = {
        'Arabic': arabic,
        'Hebrew': hebrew
    }

    doc = Document.objects.create()

    row = AttrMap({
        'pgpid': '3550',
        'language': 'Hebrew? (Tiberian vocalisation); Arabic'
    })

    import_data_cmd.add_document_language(doc, row)

    # languages with non-question mark notes are added to language_note
    assert 'Hebrew? (Tiberian vocalisation)' in doc.language_note
    assert 'Arabic' not in doc.language_note

    # languages with question marks are probable
    assert hebrew in doc.probable_languages.all()
    assert arabic in doc.languages.all()

    row.language = 'some Arabic    '
    doc.languages.clear()
    import_data_cmd.add_document_language(doc, row)
    assert arabic in doc.languages.all()

    row.language = 'missing'
    import_data_cmd.add_document_language(doc, row)
    assert 'language not found' in import_data_cmd.stdout.getvalue()


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})
def test_command_line():
    # test calling via command line
    with patch.multiple('geniza.corpus.management.commands.import_data.Command',
                        import_collections=DEFAULT,
                        import_languages=DEFAULT,
                        import_documents=DEFAULT) as mock:
        call_command('import_data')
        mock['import_collections'].assert_called_with()
        mock['import_languages'].assert_called_with()
        mock['import_documents'].assert_called_with()
