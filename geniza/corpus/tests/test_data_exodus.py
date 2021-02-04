import csv
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.core.management.base import CommandError
from django.test import override_settings
import pytest
import requests

from geniza.corpus.management.commands import data_exodus
from geniza.corpus.models import Library


@override_settings(DATA_IMPORT_URLS={})
def test_get_csv_notconfigured():
    with pytest.raises(CommandError) as err:
        data_exodus.Command().get_csv('libraries')
    assert 'not configured' in str(err)


@override_settings(DATA_IMPORT_URLS={'libraries': 'http://example.co/lib.csv'})
def test_get_csv_error():
    # simulate 404 result
    with patch.object(requests, 'get') as mockget:
        mockget.return_value.status_code = 404
        with pytest.raises(CommandError) as err:
            data_exodus.Command().get_csv('libraries')

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
        csvreader = data_exodus.Command().get_csv('libraries')
        assert isinstance(csvreader, csv.DictReader)


@pytest.mark.django_db
def test_import_libraries():
    data_exodus_cmd = data_exodus.Command()
    data_exodus_cmd.setup()
    with patch.object(data_exodus.Command, 'get_csv') as mock_lib_csv:
        mock_lib_csv.return_value = [
            {'Library': 'British Library', 'Abbreviation': 'BL'},
            {'Library': 'Bodleian Library', 'Abbreviation': 'BODL'},
            {'Library': 'Incomplete', 'Abbreviation': ''}
        ]
        data_exodus_cmd.import_libraries()
    assert Library.objects.count() == 2
    assert Library.objects.get(abbrev='BL').name == 'British Library'
    assert LogEntry.objects.filter(action_flag=ADDITION).count() == 2
