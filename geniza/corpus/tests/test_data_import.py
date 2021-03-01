from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.core.management.base import CommandError
from django.test import override_settings
import pytest
import requests

from geniza.corpus.management.commands import data_import
from geniza.corpus.models import Collection, LanguageScript


@pytest.mark.django_db
@override_settings()
def test_setup_config_error():
    del settings.DATA_IMPORT_URLS
    with pytest.raises(CommandError):
        data_import.Command().setup()


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})
def test_setup():
    data_import_cmd = data_import.Command()
    data_import_cmd.setup()
    # script user should be set
    assert data_import_cmd.script_user
    assert data_import_cmd.script_user.username == settings.SCRIPT_USERNAME


@override_settings(DATA_IMPORT_URLS={})
def test_get_csv_notconfigured():
    with pytest.raises(CommandError) as err:
        # NOTE: must consume the generator to make sure code executes
        list(data_import.Command().get_csv('libraries'))
    assert 'not configured' in str(err)


@override_settings(DATA_IMPORT_URLS={'libraries': 'http://example.co/lib.csv'})
@patch('geniza.corpus.management.commands.data_import.requests')
def test_get_csv_error(mockrequests):
    # simulate 404 result
    mockrequests.codes = requests.codes
    mockrequests.get.return_value.status_code = 404
    with pytest.raises(CommandError) as err:
        list(data_import.Command().get_csv('libraries'))

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
        data = list(data_import.Command().get_csv('libraries'))
        assert data[0].library == 'British Library'


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={'libraries': 'lib.csv'})  # must be set for command setup
@patch('geniza.corpus.management.commands.data_import.requests')
def test_import_collections(mockrequests):
    # create test collection to confirm it is removed
    Collection.objects.create(library='Junk Library', abbrev='JunkL')

    data_import_cmd = data_import.Command()
    data_import_cmd.setup()
    mockrequests.codes = requests.codes   # patch in actual response codes
    mockrequests.get.return_value.status_code = 200
    mockrequests.get.return_value.iter_lines.return_value = iter([
        b'Current List of Libraries,Library,Abbreviation,Location (current),Collection (if different from library)',
        b'BL,British Library,BL,,',
        b'BODL,Bodleian Library,BODL,,',
        b'BODL,Incomplete,,,',
        b'RNL,National Library of Russia,RNL,St. Petersburg,Firkovitch'
    ])
    data_import_cmd.import_collections()
    assert Collection.objects.count() == 3
    bl = Collection.objects.get(abbrev='BL')
    assert bl.library == 'British Library'
    assert not bl.collection
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 3
    # check that location and collection are populated when present
    rnl = Collection.objects.get(abbrev='RNL')
    assert rnl.location == 'St. Petersburg'
    assert rnl.collection == 'Firkovitch'

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        data_import_cmd.logentry_message

    # existing library records removed
    assert not Collection.objects.filter(library='Junk Library').exists()


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={'languages': 'mylangs.csv'})  # must be set for command setup
@patch('geniza.corpus.management.commands.data_import.requests')
def test_import_languages(mockrequests):
    LanguageScript.objects.create(script='Wingdings', language='English')

    data_import_cmd = data_import.Command()
    data_import_cmd.setup()
    mockrequests.codes = requests.codes   # patch in actual response codes
    mockrequests.get.return_value.status_code = 200
    mockrequests.get.return_value.iter_lines.return_value = iter([
        b'Language,Script,Vocalization,Number,',
        b'Polish,Latin,,,',
        b'Portuguese,Latin,,,',
        b',,,,note'  # should ignore empty row
    ])
    data_import_cmd.import_languages()
    mockrequests.get.assert_called_with('mylangs.csv', stream=True)
    assert LanguageScript.objects.count() == 2
    assert LanguageScript.objects.get(language='Polish').script == 'Latin'
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        data_import_cmd.logentry_message

    # existing LanguageScript records removed
    assert not LanguageScript.objects.filter(script='Wingdings').exists()
