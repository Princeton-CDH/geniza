import csv
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.core.management.base import CommandError
from django.test import override_settings
import pytest
import requests

from geniza.corpus.management.commands import data_import
from geniza.corpus.models import Library, LanguageScript


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
def test_import_libraries():
    # create test library to confirm it is removed
    Library.objects.create(name='Junk Library', abbrev='JunkL')

    data_import_cmd = data_import.Command()
    data_import_cmd.setup()
    with patch.object(data_import.Command, 'get_csv') as mock_lib_csv:
        mock_lib_csv.return_value = [
            {'Library': 'British Library', 'Abbreviation': 'BL'},
            {'Library': 'Bodleian Library', 'Abbreviation': 'BODL'},
            {'Library': 'Incomplete', 'Abbreviation': ''}
        ]
        data_import_cmd.import_libraries()
    assert Library.objects.count() == 2
    assert Library.objects.get(abbrev='BL').name == 'British Library'
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        data_import_cmd.logentry_message

    # existing library records removed
    assert not Library.objects.filter(name='Junk Library').exists()


@pytest.mark.django_db
@override_settings(DATA_IMPORT_URLS={})  # must be set for command setup
def test_import_languages():
    LanguageScript.objects.create(script='Wingdings', language='English')

    data_import_cmd = data_import.Command()
    data_import_cmd.setup()
    with patch.object(data_import.Command, 'get_csv') as mock_lang_csv:
        mock_lang_csv.return_value = [
            {'Display Name': '', 'Language': 'Polish', 'Script': 'Latin'},
            {'Display Name': '', 'Language': 'Portuguese', 'Script': 'Latin'}
        ]
        data_import_cmd.import_languages()
    assert LanguageScript.objects.count() == 2
    assert LanguageScript.objects.get(language='Polish').script == 'Latin'
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2

    assert LogEntry.objects.filter(action_flag=ADDITION)[0].change_message == \
        data_import_cmd.logentry_message

    # existing LanguageScript records removed
    assert not LanguageScript.objects.filter(script='Wingdings').exists()
