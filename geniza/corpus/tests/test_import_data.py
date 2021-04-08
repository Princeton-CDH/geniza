import datetime
import logging
from io import StringIO
from unittest.mock import DEFAULT, patch

import pytest
import requests
from attrdict import AttrMap
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings

from geniza.corpus.management.commands import import_data
from geniza.corpus.models import (Collection, Document, DocumentType, Fragment,
                                  LanguageScript)


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
# must be set for command setup
@override_settings(DATA_IMPORT_URLS={'libraries': 'lib.csv'})
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
# must be set for command setup
@override_settings(DATA_IMPORT_URLS={'languages': 'mylangs.csv'})
@patch('geniza.corpus.management.commands.import_data.requests')
def test_import_languages(mockrequests):
    LanguageScript.objects.create(script='Wingdings', language='English')

    import_data_cmd = import_data.Command()
    import_data_cmd.setup()
    mockrequests.codes = requests.codes   # patch in actual response codes
    mockrequests.get.return_value.status_code = 200
    mockrequests.get.return_value.iter_lines.return_value = iter([
        b'Language,Script,Vocalization,Number,Display name,spreadsheet_name',
        b'Polish,Latin,,,,pol',
        b'Portuguese,Latin,,,Romance,',
        b',,,,note,'  # should ignore empty row
    ])
    import_data_cmd.import_languages()
    mockrequests.get.assert_called_with('mylangs.csv', stream=True)
    assert LanguageScript.objects.count() == 2
    assert LanguageScript.objects.get(language='Polish').script == 'Latin'
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2
    assert str(LanguageScript.objects.get(language='Portuguese')) == 'Romance'

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        import_data_cmd.logentry_message

    # existing LanguageScript records removed
    assert not LanguageScript.objects.filter(script='Wingdings').exists()

    # check that language lookup was populated
    assert 'pol' in import_data_cmd.language_lookup
    assert 'romance' in import_data_cmd.language_lookup
    assert import_data_cmd.language_lookup['romance'].script == 'Latin'


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
def test_import_documents(mockrequests, caplog):
    # create test fragments & documents to confirm they are removed
    Fragment.objects.create(shelfmark='foo 1')
    Document.objects.create(notes='test doc')

    import_data_cmd = import_data.Command()
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
    with caplog.at_level(logging.INFO, logger="import"):
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
    tags = set([t.name for t in doc.tags.all()])
    assert set(['lease', 'synagogue', '11th c']) == tags
    # log entry should be created
    document_ctype = ContentType.objects.get_for_model(Document)
    assert LogEntry.objects.get(change_message=import_data_cmd.logentry_message,
                                object_id=doc.pk,
                                content_type_id=document_ctype.pk)

    doc2 = Document.objects.get(id=2292)
    assert doc2.fragments.count() == 3
    assert Fragment.objects.get(shelfmark='NA')

    # check script summary output
    output = caplog.text
    assert 'Imported 2 documents' in output
    assert '1 with joins' in output
    assert 'skipped 1' in output
    assert LogEntry.objects.get(change_message=import_data_cmd.logentry_message,
                                object_id=doc2.pk,
                                content_type_id=document_ctype.pk)


@pytest.mark.django_db
def test_add_document_language(caplog):
    import_data_cmd = import_data.Command()
    import_data_cmd.stdout = StringIO()

    # simulate language lookup already populated
    arabic = LanguageScript.objects.create(
        language='Arabic', script='Arabic', display_name='Arabic')
    hebrew = LanguageScript.objects.create(
        language='Hebrew', script='Hebrew', display_name='Hebrew')
    import_data_cmd.language_lookup = {
        'arabic': arabic,
        'hebrew': hebrew
    }

    doc = Document.objects.create()

    row = AttrMap({
        'pgpid': '3550',
        'language': 'Hebrew? (Tiberian vocalisation); arabic'
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
    assert 'language not found' in caplog.record_tuples[-1][2]


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})
def test_get_user(caplog):
    import_data_cmd = import_data.Command()
    import_data_cmd.setup()     # loads historic users from fixture
    get_user = import_data_cmd.get_user
    User = get_user_model()

    # fetch some users for testing (mixture of active and historic)
    akiva = User.objects.get(first_name="Akiva", last_name="Jackson")
    oded = User.objects.get(first_name="Oded", last_name="Zinger")
    orc = User.objects.get(first_name="Olivia Remie", last_name="Constable")

    # try fetching some of them with no cache
    with caplog.at_level(logging.DEBUG, logger="import"):
        assert get_user("Akiva Jackson") == akiva  # firstname lastname
        assert "found user" in caplog.record_tuples[-1][2]
        assert get_user("Olivia Remie Constable") == orc    # multi names
        assert "found user" in caplog.record_tuples[-1][2]
        get_user("Olivia Remie Constable")  # second call, should be cached
        assert "using cached user" in caplog.record_tuples[-1][2]

    # reset & add a name to the cache; should notify when cache is hit
    import_data_cmd.user_lookup = {"AJ": akiva}
    with caplog.at_level(logging.DEBUG, logger="import"):
        assert get_user("Akiva Jackson") == akiva  # cache miss
        assert "found user" in caplog.record_tuples[-1][2]
        assert get_user("AJ") == akiva           # cache hit
        assert "using cached user" in caplog.record_tuples[-1][2]

    # test fetching users from database using initials only; should cache
    with caplog.at_level(logging.DEBUG, logger="import"):
        assert get_user("ORC") == orc   # three initials
        assert "found user" in caplog.record_tuples[-1][2]
        assert import_data_cmd.user_lookup["ORC"] == orc    # cached initials
        assert get_user("OZ") == oded  # two initials
        assert "found user" in caplog.record_tuples[-1][2]
        assert import_data_cmd.user_lookup["OZ"] == oded
        get_user("OZ")  # test cache using initials
        assert "using cached user" in caplog.record_tuples[-1][2]

    # cache/database miss should warn and use the team user
    with caplog.at_level(logging.WARNING, logger="import"):
        assert get_user("asdf36") == import_data_cmd.team_user
        assert "couldn't find user" in caplog.record_tuples[-1][2]
        assert get_user("") == import_data_cmd.team_user
        assert "couldn't find user" in caplog.record_tuples[-1][2]


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})
def test_get_edit_history(caplog):
    import_data_cmd = import_data.Command()
    import_data_cmd.setup()
    get_edit_history = import_data_cmd.get_edit_history

    # empty dates returns empty list; nothing to do
    history = get_edit_history("", "")
    assert history == []

    # users with no dates still does nothing; no way to log an event
    history = get_edit_history("Sarah Nisenson", "")
    assert history == []

    # date with no user results in event assigned to whole team (TEAM_USER)
    history = get_edit_history("", "5/4/2016")
    assert history[0]["type"] == ADDITION
    assert history[0]["user"].username == import_data_cmd.team_user.username
    assert history[0]["date"] == datetime.date(2016, 5, 4)

    # simplest case: one user, one well-formed date -> creation event
    history = get_edit_history("Sarah Nisenson", "3/16/2018")
    assert history[0]["type"] == ADDITION
    assert history[0]["user"].username == "snisenson"
    assert history[0]["date"] == datetime.date(2018, 3, 16)

    # another simple case: two users & dates -> creation followed by revision
    history = get_edit_history("Sarah Nisenson; Emily Silkaitis",
                               "3/16/2018; 3/23/21")    # two-digit year
    assert history[0]["type"] == ADDITION
    assert history[0]["user"].username == "snisenson"
    assert history[0]["date"] == datetime.date(2018, 3, 16)
    assert history[1]["type"] == CHANGE
    assert history[1]["user"].username == "esilkaitis"
    assert history[1]["date"] == datetime.date(2021, 3, 23)

    # one user with two dates -> creation by unknown (team) followed by revision
    history = get_edit_history("Emily Silkaitis",
                               "3/16/2018; 03/2021")  # missing day value
    assert history[0]["type"] == ADDITION
    assert history[0]["user"].username == import_data_cmd.team_user.username
    assert history[0]["date"] == datetime.date(2018, 3, 16)
    assert history[1]["type"] == CHANGE
    assert history[1]["user"].username == "esilkaitis"
    assert history[1]["date"] == datetime.date(2021, 3, 1)

    # coauthored creation -> simultaneous events
    with caplog.at_level(logging.DEBUG, logger="import"):
        history = get_edit_history("Amir Ashur and Oded Zinger", "8/1/2017")
        assert "found coauthored event" in caplog.record_tuples[-1][2]
        assert history[0]["type"] == ADDITION
        assert history[0]["user"].username == "aashur"
        assert history[0]["date"] == datetime.date(2017, 8, 1)
        assert history[1]["type"] == ADDITION   # two creation events
        assert history[1]["user"].username == "ozinger"
        assert history[1]["date"] == datetime.date(2017, 8, 1)

    # coauthored creation followed by revision
    with caplog.at_level(logging.DEBUG, logger="import"):
        history = get_edit_history("Amir Ashur and Oded Zinger; Emily Silkaitis",
                                   "8/1/2017; November 2020")   # literal month
        assert "found coauthored event" in caplog.record_tuples[-1][2]
        assert history[0]["type"] == ADDITION
        assert history[0]["user"].username == "aashur"
        assert history[0]["date"] == datetime.date(2017, 8, 1)
        assert history[1]["type"] == ADDITION   # two creation events
        assert history[1]["user"].username == "ozinger"
        assert history[1]["date"] == datetime.date(2017, 8, 1)
        assert history[2]["type"] == CHANGE
        assert history[2]["user"].username == "esilkaitis"
        assert history[2]["date"] == datetime.date(2020, 11, 1)


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})
def test_log_edit_history():
    import_data_cmd = import_data.Command()
    import_data_cmd.setup()
    log_edit_history = import_data_cmd.log_edit_history
    dtype = import_data_cmd.content_types[Document]
    User = get_user_model()

    # simplest case: no edit history, only import event as an ADDITION
    doc1 = Document.objects.create()
    log_edit_history(doc1, [])
    entries = LogEntry.objects.filter(object_id=doc1.pk,
                                      content_type_id=dtype.pk)
    assert entries.count() == 1
    assert entries[0].user == import_data_cmd.script_user
    assert entries[0].action_flag == ADDITION
    assert entries[0].action_time.date() == datetime.date.today()

    # edit history with only one creation event plus import
    doc2 = Document.objects.create()
    user = User.objects.get(username="esilkaitis")
    date = datetime.date(2017, 5, 9)
    log_edit_history(doc2, [{"type": ADDITION, "user": user, "date": date}])
    entries = LogEntry.objects.filter(object_id=doc2.pk,
                                      content_type_id=dtype.pk)
    assert entries.count() == 2
    assert entries[0].user == import_data_cmd.script_user
    assert entries[0].action_flag == ADDITION
    assert entries[0].action_time.date() == datetime.date.today()
    assert entries[1].user == user
    assert entries[1].action_flag == ADDITION
    assert entries[1].action_time.date() == date

    # edit history with multiple events/coauthored event
    doc3 = Document.objects.create()
    user = User.objects.get(username="esilkaitis")
    user2 = User.objects.get(username="ozinger")
    user3 = User.objects.get(username="aashur")
    date = datetime.date(2017, 5, 9)
    date2 = datetime.date(2020, 11, 20)
    log_edit_history(doc3, [
        {"type": ADDITION, "user": user2, "date": date},
        {"type": ADDITION, "user": user3, "date": date},
        {"type": CHANGE, "user": user, "date": date2},
    ])
    entries = LogEntry.objects.filter(object_id=doc3.pk,
                                      content_type_id=dtype.pk)
    assert entries.count() == 4
    assert entries[0].user == import_data_cmd.script_user
    assert entries[0].action_flag == ADDITION
    assert entries[0].action_time.date() == datetime.date.today()
    assert entries[1].user == user
    assert entries[1].action_flag == CHANGE
    assert entries[1].action_time.date() == date2
    assert entries[2].user == user2
    assert entries[2].action_flag == ADDITION
    assert entries[2].action_time.date() == date
    assert entries[3].user == user3
    assert entries[3].action_flag == ADDITION
    assert entries[3].action_time.date() == date


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


@pytest.mark.django_db
def test_update_document_id_sequence():
    import_data_cmd = import_data.Command()
    import_data_cmd.stdout = StringIO()

    # create document with pgpid specified
    doc = Document.objects.create(id=3000)
    # update id sequence
    import_data_cmd.update_document_id_sequence()
    # retrieve the next value
    cursor = connection.cursor()
    cursor.execute("select nextval('corpus_document_id_seq')")
    result = cursor.fetchone()
    assert result == (doc.id + 1, )
