import glob
import json
import os.path

import click
from eulxml import xmlmap
from eulxml.xmlmap import teimap
from flask import current_app
from flask.cli import with_appcontext
from parasolr.query import SolrQuerySet
from parasolr.solr.client import SolrClient
import requests


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


@click.command()
@with_appcontext
def transcription_iiif():
    # first pass at creating iiif annotations with tei transcriptions
    # (currently only for items with IIIF and transcriptions)

    data_dir = current_app.config['DATA_DIR']
    # use a subdir for iiif manifests; make sure it exists
    manifest_dir = os.path.join(data_dir, 'iiif', 'manifests')
    os.makedirs(manifest_dir, exist_ok=True)
    # and another subdir for annotations
    annotation_dir = os.path.join(data_dir, 'iiif', 'annotations')
    os.makedirs(annotation_dir, exist_ok=True)

    with open(os.path.join(data_dir, 'transcriptions.json')) as transcriptionsfile:
        transcriptions = json.load(transcriptionsfile)

    solr = SolrClient(current_app.config['SOLR_URL'],
                      current_app.config['SOLR_CORE'])
    # find documents that have a IIIF link that ALSO have transcription
    iiifdocs = SolrQuerySet(solr).filter(iiif_link_s='*',
                                         transcription_txt='*')
    print('%d documents' % iiifdocs.count())
    for doc in iiifdocs[:2000]:
        # filenames where the file will be written
        base_filename = '%s.json' % doc['id']
        # write the new annotation list to a file
        annotation_filename = os.path.join(annotation_dir, base_filename)
        # write out a local copy of the modified manifest
        manifest_filename = os.path.join(manifest_dir, base_filename)

        # if the files already exist, don't regenerate them
        if all(os.path.exists(f) for f in
               [manifest_filename, annotation_filename]):
            continue

        # get the manifest for this document
        response = requests.get(doc['iiif_link_s'])
        if response.status_code != requests.codes.ok:
            print('Error retrieving manifest: %s' % doc['iiif_link_s'])
            continue
        try:
            manifest = response.json()
        except json.decoder.JSONDecodeError as err:
            print('Error decoding json: %s\n%s' % (err, doc['iiif_link_s']))
            continue

        # for now, assume simple structure, single sequence
        # for now, associate the annotation with the first image
        canvas1 = manifest['sequences'][0]['canvases'][0]
        # need id, width, and height
        canvas_id = canvas1['@id']
        canvas_width = canvas1['width']
        canvas_height = canvas1['height']

        annotation_list = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            # placeholder id; should probably be unique!
            "@id": "https://cdh.geniza.princeton.edu/iiif/canvas/AnnotationList",
            "@type": "sc:AnnotationList",
            "resources": []
        }

        # for each block
        for i, text_block in enumerate(transcriptions[doc['id']]['blocks']):
            text_lines = '%s<br/>%s' % (text_block['label'],
                                        '<br/>'.join(text_block['lines']))
            annotation = {
                # uri for this annotation; make something up
                "@id": "https://cdh.geniza.princeton.edu/iiif/%s/list/%d" % \
                       (doc['id'], i),
                "@type": "oa:Annotation",
                "motivation": "sc:painting",
                "resource": {
                    "@type": "cnt:ContentAsText",
                    "format": "text/html",
                    # language todo
                    "chars": "<p dir='rtl'>%s</p>" % text_lines
                },
                # annotate the entire canvas for now
                "on": "%s#xywh=0,0,%d,%d" % (canvas_id, canvas_width,
                                             canvas_height)
            }
            annotation_list['resources'].append(annotation)

        with open(annotation_filename, 'w') as outfile:
            json.dump(annotation_list, outfile, indent=2)

        # add the annotation to our copy of the manifest
        canvas1['otherContent'] = [
            {
                "@context": "http://iiif.io/api/presentation/2/context.json",
                "@id": 'http://FLASK_URL/iiif/annotations/%s' % base_filename,
                "@type": "sc:AnnotationList"
            }
        ]

        with open(manifest_filename, 'w') as outfile:
            json.dump(manifest, outfile, indent=2)
