#!/usr/bin/env python
'''
An HTTP server that proxies requests to solr to search for similar incipits.

Copy local_settings.cfg.sample to local_settings.cfg and configure
as appropriate for your environment.

Run a debug server for development with:
    $ export FLASK_APP=scripts/server.py FLASK_ENV=development
    $ flask run

'''

from flask import Flask, g, jsonify, render_template, request
from parasolr.query import SolrQuerySet
from parasolr.solr.client import SolrClient

from scripts import __version__

# create a new flask app from this module
app = Flask(__name__)
# load configuration from local settings
app.config.from_pyfile('local_settings.cfg')


@app.route('/')
def root():
    '''Display version info and a basic html search form.'''
    return render_template('index.html', version=__version__,
                           env=app.config.get('ENV', None))


@app.route('/search', methods=['GET', 'POST'])
def search():
    '''Search for an incipit and return a list of matching results.'''
    if request.method == 'POST':
        search_term = request.form['geniza_search']
        output_format = request.form.get('format', '')
    elif request.method == 'GET':
        search_term = request.args.get('geniza_search', '')
        output_format = request.args.get('format', '')

    queryset = SolrQuerySet(get_solr())
    if search_term:
        queryset = queryset.search(description_txt=search_term) \
            .order_by('-score') \
            .only('id', 'description_txt', 'shelfmark_current_s', 'library_s', 'score')

    results = queryset.get_results(rows=20)

    # if html response was requested, render results.html template
    if output_format == 'html':
        return render_template('results.html', results=results,
                               total=queryset.count(),
                               search_term=search_term,
                               version=__version__,
                               env=app.config.get('ENV', None))

    # by default, return JSON
    return jsonify(results)


def get_solr():
    '''Get a shared-per-request connection to solr, creating if none exists.'''
    # see https://flask.palletsprojects.com/en/1.1.x/api/#flask.g
    if 'solr' not in g:
        g.solr = SolrClient(app.config['SOLR_URL'], app.config['SOLR_CORE'])
    return g.solr
