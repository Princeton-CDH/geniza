import glob
import json
import os.path

import click
from eulxml import xmlmap
from eulxml.xmlmap import teimap
from flask import current_app
from flask.cli import with_appcontext


class GenizaTei(teimap.Tei):
    # extend eulxml TEI to add mappings for the fields we care about
    pgpid = xmlmap.IntegerField('tei:teiHeader//tei:idno[@type="PGP"]')
    lines = xmlmap.NodeListField('tei:text/tei:body/tei:div/tei:l',
                                 teimap.TeiLine)


@click.command()
@with_appcontext
def transcriptions():
    xml_dir = current_app.config['XML_TRANSCRIPTIONS_DIR']

    data = {}

    for xmlfile in glob.iglob(os.path.join(xml_dir, '*.xml')):
        print(xmlfile)

        tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
        data[tei.pgpid] = [str(l) for l in tei.lines]

    with open('data/geniza-transcriptions.json', 'w') as outfile:
        json.dump(data, outfile, indent=4)
