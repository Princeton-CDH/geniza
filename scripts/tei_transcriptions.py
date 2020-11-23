import glob
import json
import os.path

import click
from eulxml import xmlmap
from eulxml.xmlmap import teimap
from flask import current_app
from flask.cli import with_appcontext


class GenizaTeiLine(teimap.TeiLine):
    name = xmlmap.StringField('local-name(.)')
    lang = xmlmap.StringField('@xml:lang|tei:span/@xml:lang')


class MainText(teimap.TeiDiv):
    lines = xmlmap.NodeListField('tei:l|tei:label',
                                 GenizaTeiLine)


class GenizaTei(teimap.Tei):
    # extend eulxml TEI to add mappings for the fields we care about
    pgpid = xmlmap.IntegerField('tei:teiHeader//tei:idno[@type="PGP"]')
    # normally main text content is under text/body/div; but at least one document has no div
    text = xmlmap.NodeField('tei:text/tei:body/tei:div|tei:text/tei:body[not(tei:div)]', MainText)
    lines = xmlmap.NodeListField('tei:text/tei:body/tei:div/tei:l',
                                 GenizaTeiLine)
    labels = xmlmap.NodeListField('tei:text/tei:body/tei:div/tei:label',
                                  GenizaTeiLine)   # not really a line...


@click.command()
@with_appcontext
def transcriptions():
    xml_dir = current_app.config['XML_TRANSCRIPTIONS_DIR']
    data_dir = current_app.config['DATA_DIR']

    data = {}

    for xmlfile in glob.iglob(os.path.join(xml_dir, '*.xml')):
        # print(os.path.basename(xmlfile))
        print(xmlfile)

        tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)

        blocks = []
        label = []
        lines = []
        languages = set()
        for line in tei.text.lines:
            if line.name == 'label':
                # append current text block if set, and initialize a new one
                if lines:
                    blocks.append({
                        'label': '\n'.join(label),
                        'lines': lines,
                        'languages': list(languages)
                    })
                    label = []
                    lines = []

                # store the label; sometimes there are two in a row
                label.append(str(line))

            elif line.name == 'l':
                if line.lang:
                    # NOTE: will need to add logic to detect languages;
                    # language tags in the xml are sparse
                    languages.add(line.lang)
                lines.append(str(line))

        if lines:
            blocks.append({
                'label': '\n'.join(label),
                'lines': lines,
                'languages': list(languages)
            })

        docdata = {
            'blocks': blocks,
            'lines': [str(l) for l in tei.text.lines]
        }
        data[tei.pgpid] = docdata

    with open(os.path.join(data_dir,
                           'transcriptions.json'), 'w') as outfile:
        json.dump(data, outfile, indent=4)
