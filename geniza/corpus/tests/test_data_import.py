import csv
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
        data_import.Command().get_csv('libraries')
    assert 'not configured' in str(err)


@override_settings(DATA_IMPORT_URLS={'libraries': 'http://example.co/lib.csv'})
def test_get_csv_error():
    # simulate 404 result
    with patch.object(requests, 'get') as mockget:
        mockget.return_value.status_code = 404
        with pytest.raises(CommandError) as err:
            data_import.Command().get_csv('libraries')

        mockget.assert_called_with(settings.DATA_IMPORT_URLS['libraries'],
                                   stream=True)

    assert 'Error accessing' in str(err)


@override_settings(DATA_IMPORT_URLS={'libraries': 'http://example.co/lib.csv'})
def test_get_csv_success():
    # simulate 200 result
    with patch.object(requests, 'get') as mockget:
        mockget.return_value.status_code = 200
        mockget.return_value.iter_lines.return_value = [
            'Library,Abbreviation',
            'British Library,BL',
            'Bodleian Library,BODL'
        ]
        csvreader = data_import.Command().get_csv('libraries')
        assert isinstance(csvreader, csv.DictReader)


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})  # must be set for command setup
def test_import_collections():
    # create test collection to confirm it is removed
    Collection.objects.create(library='Junk Library', abbrev='JunkL')

    data_import_cmd = data_import.Command()
    data_import_cmd.setup()
    with patch.object(data_import.Command, 'get_csv') as mock_lib_csv:
        mock_lib_csv.return_value = [
            {'Library': 'British Library', 'Abbreviation': 'BL',
             'Location (current)': '',
             'Collection (if different from library)': ''},
            {'Library': 'Bodleian Library', 'Abbreviation': 'BODL',
             'Location (current)': '',
             'Collection (if different from library)': ''},
            {'Library': 'Incomplete', 'Abbreviation': '',
             'Location (current)': '',
             'Collection (if different from library)': ''},
            {'Library': 'National Library of Russia', 'Abbreviation': 'RNL',
             'Location (current)': 'St. Petersburg',
             'Collection (if different from library)': 'Firkovitch'}
        ]
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
@override_settings(DATA_IMPORT_URLS={})  # must be set for command setup
def test_import_languages():
    LanguageScript.objects.create(script='Wingdings', language='English')

    data_import_cmd = data_import.Command()
    data_import_cmd.setup()
    with patch.object(data_import.Command, 'get_csv') as mock_lang_csv:
        mock_lang_csv.return_value = [
            {'Language': 'Polish', 'Script': 'Latin'},
            {'Language': 'Portuguese', 'Script': 'Latin'},
            {'Language': '', 'Script': ''}  # should ignore empty row
        ]
        data_import_cmd.import_languages()
    assert LanguageScript.objects.count() == 2
    assert LanguageScript.objects.get(language='Polish').script == 'Latin'
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        data_import_cmd.logentry_message

    # existing LanguageScript records removed
    assert not LanguageScript.objects.filter(script='Wingdings').exists()
