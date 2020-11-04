import codecs
import csv
import json

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

    with open('data/transcriptions.json') as transcriptionsfile:
        transcriptions = json.load(transcriptionsfile)

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
    index_data = []
    for row in rows:
        tags = [tag.strip() for tag in row['Tags'].split('#') if tag.strip()]
        # create a combined, sorted version of tag list for grouping
        # records with the same set of tags
        sorted_tags = tags.copy()
        sorted_tags.sort()
        tagset = '|'.join(sorted_tags)

        extlink = row['Link to image']
        iiif_link = None
        # cambridge iiif manifest links use the same id as view links
        if 'cudl.lib.cam.ac.uk' in extlink:
            iiif_link = extlink.replace('/view/', '/iiif/')

        pgpid = row['PGPID']
        text = text_blob = None
        if pgpid in transcriptions:
            # TBD: should labels also be searchable ?
            # throw everything into a text blob
            text_blob = ' '.join(transcriptions[pgpid]['lines'])
            # but also index as lines so highlighting can return single lines
            # instead of the whole text
            text = transcriptions[pgpid]['lines']
            # index language from spreadsheet?
            # TODO: languages will need to be auto-detected; may be useful
            # to check against language from the spreadsheet
            # print(row['Language (optional)'])

        index_data.append({
            # use PGPID as Solr identifier
            'id': pgpid,
            'description_txt': row['Description'],
            'type_s': row['Type'],
            'library_s': row['Library'],
            'shelfmark_s': row['Shelfmark - Current'],
            'shelfmark_txt': row['Shelfmark - Current'],
            'tags_txt': tags,
            'tags_ss': tags,
            'tagset_s': tagset,
            'link_s': extlink or None,
            'iiif_link_s': iiif_link,
            'editors_txt': row['Editor(s)'] or None,
            'translators_txt': row['Translator (optional)'] or None,
            'transcription_lines_txt': text,
            'transcription_txt': text_blob
        })

    solr.update.index(index_data, commitWithin=1000)

    print(f'Indexed {len(rows):,} records')

#MR: Library, shelfmark, description, tags, editor(s), translator — tentative list, let’s discuss.

