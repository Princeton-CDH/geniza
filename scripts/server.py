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


@app.route('/clusters/', methods=['GET'])
def clusters():
    # use a facet pivot query to get tags that occur together on at
    # at least 50 documents
    sqs = SolrQuerySet(get_solr()) \
        .facet('tags_ss', pivot='tags_ss,tags_ss', **{'pivot.mincount': 50})
    facets = sqs.get_facets()

    # iterate over the facet pivots to generate a unique list of pairs & counts
    tag_pairs = []
    tag_pair_counts = {}
    for tag_pivot in facets.facet_pivot['tags_ss,tags_ss']:
        tag_a = tag_pivot['value']
        for pivot in tag_pivot['pivot']:
            tag_b = pivot['value']
            # every pivot repeats the first tag; skip that one
            if tag_b == tag_a:
                continue
            tag_pair = '/'.join([tag_a, tag_b])
            # each pair will show up twice; only add it the first time
            alt_tag_pair = '/'.join([tag_b, tag_a])
            if alt_tag_pair in tag_pairs:
                continue
            tag_pairs.append(tag_pair)
            tag_pair_counts[tag_pair] = pivot['count']

    # check for currently selected cluster
    selected_cluster = request.args.get('cluster', None)

    # combine tag pairs & counts into a format that will be easy to render
    clusters = []
    current_cluster_label = None
    for tag_pair in tag_pairs:
        label = ' '.join('#%s' % tag for tag in tag_pair.split('/'))
        selected = tag_pair == selected_cluster
        if selected:
            current_cluster_label = label
        clusters.append({
            'value': tag_pair,
            'label': label,
            'count': tag_pair_counts[tag_pair],
            'selected': selected
        })
    # sort by count, highest counts first
    clusters = sorted(clusters, key=lambda i: i['count'], reverse=True)

    # if a cluster is selected, find all documents
    documents = cluster_tags = groups = None
    if selected_cluster:
        cluster_tags = selected_cluster.split('/')
        # search for items that match both tags
        # group them by distinct tag sets, and then expand
        # to return everything in the collapsed group
        tag_query = ' AND '.join(['"%s"' % tag for tag in cluster_tags])
        document_sqs = SolrQuerySet(get_solr()) \
            .filter(tags_ss='(%s)' % tag_query) \
            .filter('{!collapse field=tagset_s }') \
            .raw_query_parameters(
                expand='true', **{'expand.rows': 1000})

        documents = document_sqs.get_results(rows=1000)
        groups = document_sqs.get_expanded()

    return render_template(
        'clusters.html', clusters=clusters,
        current_cluster=current_cluster_label,
        current_cluster_count=tag_pair_counts[selected_cluster] if selected_cluster else None,
        current_tags=cluster_tags,
        documents=documents, groups=groups,
        version=__version__, env=app.config.get('ENV', None))


def get_solr():
    '''Get a shared-per-request connection to solr, creating if none exists.'''
    # see https://flask.palletsprojects.com/en/1.1.x/api/#flask.g
    if 'solr' not in g:
        g.solr = SolrClient(app.config['SOLR_URL'], app.config['SOLR_CORE'])
    return g.solr
