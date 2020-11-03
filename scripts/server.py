#!/usr/bin/env python
'''
An HTTP server that proxies requests to solr to search for similar incipits.

Copy local_settings.py.sample to local_settings.py and configure
as appropriate for your environment.

Run a debug server for development with:
    $ export FLASK_APP=scripts/server.py FLASK_ENV=development
    $ flask run

'''

from flask import Flask, g, render_template, request
from parasolr.query import SolrQuerySet
from parasolr.solr.client import SolrClient

from scripts import __version__
from scripts import index, tei_transcriptions


# create a new flask app from this module
app = Flask(__name__)
# load configuration from local settings
app.config.from_pyfile('local_settings.py')
# register commands
app.cli.add_command(index.index)
app.cli.add_command(tei_transcriptions.transcriptions)


@app.route('/', methods=['GET'])
def search():
    '''Search PGP records and display return a list of matching results.'''
    search_terms = request.args.get('keywords', '')

    #: keyword search field query alias field syntax
    search_query = "{!dismax qf=$keyword_qf pf=$keyword_pf ps=2 v=$search_terms}"

    queryset = SolrQuerySet(get_solr())
    # highlighting lines only instead of text blob; lines in full text are so
    # short the highlight snippets end up getting the whole thing in many cases
    if search_terms:
        queryset = queryset.search(search_query) \
            .raw_query_parameters(search_terms=search_terms) \
            .highlight('transcription_lines_txt', snippets=3, method='unified') \
            .order_by('-score').only('*', 'score')

    results = queryset.get_results(rows=50)

    # copied from pemm
    if results and search_terms:
        # patch highlighted transcription lines into the main result
        # to avoid accessing separately in the template or json
        highlights = queryset.get_highlighting()
        for i, result in enumerate(results):
            highlighted_text = highlights[result['id']] \
                .get('transcription_lines_txt', None)
            if highlighted_text:
                result['transcription_highlights'] = highlighted_text[0]

    return render_template('results.html', results=results,
                           total=queryset.count(),
                           search_term=search_terms,
                           version=__version__,
                           env=app.config.get('ENV', None))


def get_solr():
    '''Get a shared-per-request connection to solr, creating if none exists.'''
    # see https://flask.palletsprojects.com/en/1.1.x/api/#flask.g
    if 'solr' not in g:
        g.solr = SolrClient(app.config['SOLR_URL'], app.config['SOLR_CORE'])
    return g.solr
