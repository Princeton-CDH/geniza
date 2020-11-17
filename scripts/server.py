#!/usr/bin/env python
'''
An HTTP server that proxies requests to solr to search for similar incipits.

Copy local_settings.py.sample to local_settings.py and configure
as appropriate for your environment.

Run a debug server for development with:
    $ export FLASK_APP=scripts/server.py FLASK_ENV=development
    $ flask run

'''
from collections import defaultdict
from logging.config import dictConfig

from flask import Flask, g, render_template, request
from parasolr.query import SolrQuerySet
from parasolr.solr.client import SolrClient

from scripts import __version__
from scripts import index, tei_transcriptions


dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'DEBUG',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    },
    'parasolr': {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False
    },
})


# create a new flask app from this module
app = Flask(__name__)
# load configuration from local settings
app.config.from_pyfile('local_settings.py')
# register commands
app.cli.add_command(index.index)
app.cli.add_command(tei_transcriptions.transcriptions)

#: keyword search field query alias field syntax
search_query = "{!dismax qf=$keyword_qf pf=$keyword_pf ps=2 v=$search_terms}"


@app.route('/', methods=['GET'])
def search():
    '''Search PGP records and display return a list of matching results.'''
    search_terms = request.args.get('keywords', '')
    tags = request.args.getlist('tag')
    tag_logic = request.args.get('tag_logic', 'logical_or')

    queryset = SolrQuerySet(get_solr()) \
        .facet('tags_ss', mincount=1, limit=150)
    # highlighting lines only instead of text blob; lines in full text are so
    # short the highlight snippets end up getting the whole thing in many cases
    if search_terms:
        queryset = queryset.search(search_query) \
            .raw_query_parameters(search_terms=search_terms) \
            .highlight('transcription_lines_txt', snippets=3, method='unified') \
            .order_by('-score').only('*', 'score')

    if tags:
        # find documents that match any of the selected tags
        if tag_logic == 'logical_or':
            queryset = queryset.filter(tags_ss__in=tags)
        else:
            # find documents that match all of the selected tags
            query_string = '(%s)' % ' AND '.join(['"%s"' % tag for tag in tags])
            queryset = queryset.filter(tags_ss=query_string)

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
                result['transcription_highlights'] = highlighted_text

    return render_template('results.html', results=results,
                           total=queryset.count(),
                           search_term=search_terms,
                           facets=queryset.get_facets(),
                           selected_tag_logic=tag_logic,
                           version=__version__,
                           selected_tags=tags,
                           env=app.config.get('ENV', None))


@app.route('/clusters/', methods=['GET'])
def clusters():
    # use a facet pivot query to get tags that occur together on at
    # at least 50 documents

    search_terms = request.args.get('keywords', '')

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
    documents = cluster_tags = groups = highlights = total = None
    doc_clusters = defaultdict(list)
    if selected_cluster or search_terms:
        document_sqs = SolrQuerySet(get_solr())

        # if search terms are present, filter by search terms
        # configure highlighting, and order by relevance
        if search_terms:
            document_sqs = document_sqs.search(search_query) \
                .raw_query_parameters(search_terms=search_terms) \
                .highlight('transcription_lines_txt', snippets=3, method='unified') \
                .highlight('description_txt', snippets=3, method='unified') \
                .order_by('-score')

        # otherwise get all documents for the selected cluster
        elif selected_cluster:
            cluster_tags = selected_cluster.split('/')
            # search for items that match both tags
            tag_query = ' AND '.join(['"%s"' % tag for tag in cluster_tags])
            # group documents by distinct tag sets, and then expand
            # to return everything in the collapsed group
            document_sqs = document_sqs.filter(tags_ss='(%s)' % tag_query) \
                .filter('{!collapse field=tagset_s }') \
                .raw_query_parameters(
                    expand='true', **{'expand.rows': 1000})

        documents = document_sqs.get_results(rows=1000)
        # groups are for cluster browse only
        groups = document_sqs.get_expanded()
        total = document_sqs.count()
        # highlight is for search only
        highlights = document_sqs.get_highlighting()

        # for search, determine which clusters each document belongs to
        if search_terms:
            for doc in documents:
                for cluster in clusters:
                    cluster_tags = cluster['value'].split('/')
                    # if all tags in a cluster occur in this document,
                    # add cluster label and value to the list
                    if all(ctag in doc.get('tags_ss', []) for ctag in cluster_tags):
                        doc_clusters[doc['id']].append({
                            'value': cluster['value'],
                            'label': cluster['label']
                        })

    return render_template(
        'clusters.html', clusters=clusters,
        current_cluster=current_cluster_label,
        current_cluster_count=tag_pair_counts[selected_cluster] if selected_cluster else None,
        current_tags=cluster_tags,
        documents=documents, groups=groups,
        document_clusters=doc_clusters,
        total=total,
        search_term=search_terms, highlights=highlights,
        search_words=search_terms.split(),
        version=__version__, env=app.config.get('ENV', None))


def get_solr():
    '''Get a shared-per-request connection to solr, creating if none exists.'''
    # see https://flask.palletsprojects.com/en/1.1.x/api/#flask.g
    if 'solr' not in g:
        g.solr = SolrClient(app.config['SOLR_URL'], app.config['SOLR_CORE'])
    return g.solr
