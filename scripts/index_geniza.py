'''
Requires Python 3.7

Requires parasolr:

    pip install parasolr

Create a solr core with the local solr:

    solr create_core -c geniza

Run this script, providing solr connection details and a path
to the CSV file you'd like to index.

    python index_geniza.py http://localhost:8983/solr/ geniza \
        /path/to/data.csv

python index_geniza.py http://localhost:8983/solr/ geniza pgp-metadata.csv

'''

import argparse
import pandas as pd
import os
from types import SimpleNamespace

from parasolr.solr.client import SolrClient


def test_df(df):
    """Validate the input csv to ensure that it conforms to expected input"""
    # Ensure PGPID is unique
    assert df['PGPID'].unique().shape[0] == df.shape[0]

    # TODO: insert good-tables-esque validation


def index_geniza(solr_url, solr_core, csv_path):
    '''Connect to Solr, clear the index, and index data
     from the specified CSV file.'''

    solr = SolrClient(solr_url, solr_core)

    # clear the index in case identifiers have changed
    solr.update.delete_by_query('*:*')

    df = pd.read_csv(csv_path)
    # Ensure the CSV file contains the expected columns
    expected_columns = ['PGPID', 'Description', 'Library', 
        'Shelfmark - Current', 'Link to image']
    df = df[expected_columns]
    
    test_df(df)

    # index dataframe into Solr
    solr.update.index([{
        # identifier required for current Solr config
        'id': row['PGPID'],
        'description_txt': row['Description'],
        'library_s': row['Library'],
        'shelfmark_current_s': row['Shelfmark - Current'],
        'link_s': row['Link to image']
    } for i, row in df.iterrows()])

    # Ensure the CSV file contains the expected columns
    expected_columns = ['PGPID', 'Description', 'Library', 
        'Shelfmark - Current', 'Link to image']
    df = df[expected_columns]

    print(f'Indexed {df.shape[0]} records')


def get_env_opts():
    # check for environment variable configuration
    return SimpleNamespace(
        solr_url=os.getenv('GENIZA_SOLR_URL', None),
        solr_core=os.getenv('GENIZA_SOLR_CORE', None),
        csvpath=os.getenv('GENIZA_CSVPATH', None)
    )


def get_cli_args():
    # get command-line arguments
    parser = argparse.ArgumentParser(
        description='Index Geniza CSV into a given solr core.')
    parser.add_argument('solr_url', help='Solr URL')
    parser.add_argument('solr_core', help='Solr core')
    parser.add_argument('csvpath', help='Path to CSV file')
    return parser.parse_args()

if __name__ == "__main__":
    # check environment variables for configuration first
    args = get_env_opts()
    # if not set, use command line args
    if not all([args.solr_url, args.solr_core, args.csvpath]):
        args = get_cli_args()

    index_geniza(args.solr_url, args.solr_core, args.csvpath)
