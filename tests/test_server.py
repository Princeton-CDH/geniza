from unittest.mock import Mock, patch

from flask import g
import pytest

from scripts import __version__, server

# see the flask docs for an explanation of creating an example test client:
# https://flask.palletsprojects.com/en/1.1.x/testing/#the-testing-skeleton

# see also the docs on mocking the 'g' context object:
# https://flask.palletsprojects.com/en/1.1.x/testing/#faking-resources


@pytest.fixture
def client():
    server.app.config['TESTING'] = True
    with server.app.test_client() as client, server.app.app_context():
            yield client


def test_index(client):
    # check home page
    with patch('scripts.server.SolrQuerySet') as mock_solrqueryset:
        mock_solrqueryset.return_value.get_results \
            .return_value.__len__.return_value = 8
        mock_solrqueryset.return_value.count.return_value = 100
        rv = client.get('/')
        assert 'version %s' % __version__ in rv.data.decode()
        assert b'<form action="/" method="get"' in rv.data
        assert b'<input type="text" name="keywords"' in rv.data
        assert b'Showing 8 of 100 results' in rv.data


@patch('scripts.server.SolrClient')
def test_get_solr(mocksolrclient, client):
    assert 'solr' not in g
    # should initialize solr client and store in app context global
    server.get_solr()
    assert 'solr' in g
    mocksolrclient.assert_called_with(server.app.config['SOLR_URL'],
                                      server.app.config['SOLR_CORE'])

    # if called again, should not re-initialize
    mocksolrclient.reset_mock()
    server.get_solr()
    mocksolrclient.assert_not_called()
