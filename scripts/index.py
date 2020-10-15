import codecs
import csv

import click
from flask import current_app
from flask.cli import with_appcontext
import requests

from parasolr.solr.client import SolrClient


@click.command()
@with_appcontext
def index():
    solr = SolrClient(current_app.config['SOLR_URL'],
                      current_app.config['SOLR_CORE'])

    # clear the index in case any records have been removed or merged
    solr.update.delete_by_query('*:*')

    # load CSV data via URL
    response = requests.get(current_app.config['METADATA_CSV_URL'],
                            stream=True)
    if response.status_code != requests.codes.ok:
        print('Error accessing CSV: %s' % response)
        # error code / exception ?
        return

    csvreader = csv.DictReader(codecs.iterdecode(response.iter_lines(),
                               'utf-8'))
    rows = list(csvreader)

    # check that pgp ids are unique
    pgpids = [row['PGPID'] for row in rows]
    if len(pgpids) != len(set(pgpids)):
        print('Warning: PGPIDs are not unique!')

    # add a quick progress bar here?

    # index pgp data into Solr
    solr.update.index([{
        # use PGPID as Solr identifier
        'id': row['PGPID'],
        'description_txt': row['Description'],
        'type_s': row['Type'],
        'library_s': row['Library'],
        'shelfmark_s': row['Shelfmark - Current'],
        'shelfmark_txt': row['Shelfmark - Current'],
        'tags_txt': [tag.strip() for tag in row['Tags'].split('#') if tag.strip() != ''],
        'tags_ss': [tag.strip() for tag in row['Tags'].split('#') if tag.strip() != ''],
        'link_s': row['Link to image'],
        'iiif_link_s': (
            row['Link to image'].replace('/view/', '/iiif/') 
            if 'cudl.lib.cam.ac.uk' in row['Link to image']
            else None
        ),
        'editors_txt': row['Editor(s)'],
        'translators_txt': row['Translator (optional)']
    } for row in rows], commitWithin=100)

    print(f'Indexed {len(rows):,} records')

#MR: Library, shelfmark, description, tags, editor(s), translator — tentative list, let’s discuss.

