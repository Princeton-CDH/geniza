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


# first pass at creating iiif annotations with tei transcriptions

# - iterate over metadata csv (or use solr?)
# - identify documents with iiif link (cudl only for now) that ALSo have a transcription
# - generate iiif annotation list; one annotation for each block in the tei
# - get a local copy of the iiif manifest and add the annotation list
# - generate test mirador viewer with the manifests loaded (static? in flask?)


annotation_list_template = {
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@id": "http://localhost:8003/coin/canvas/AnnotationList",
    "@type": "sc:AnnotationList",
    "resources": [
        {
            "@id": "https://images.lib.cam.ac.uk/iiif/MS-ADD-02586-000-00001.jp2",
            "@type": "oa:Annotation",
            "motivation": "sc:painting",
            "resource": {
                "@type": "cnt:ContentAsText",
                "format": "text/html",
                "chars": "<p style='direction:rtl'>מעידים אנו <b>חתומי</b> מטה מה שהיה בפנינו באחד בשבת יום אחד ועשרים מחדש סיון בשנת אתקמד לשטרות<br/>למניננו אשר הורגלנו למנות בו פה בפסטאט מצרים אשר על נהר נילוס היא יושבת הדרת אדוננו הנגיד<br/>הגדול מרנו ורבנו אברהם הרב המובהק [. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .]לב.[. . . . . . . . .<br/>לפנינו אלשיך אבו אלפכר הזקן היקר בן מר ורב עמרם הזקן הנכבד נע ויאמר לנו היו עלי עדים וקנו ממני<br/>בכל לשון שלזכות וכתבו וחתמו ותנו לידי בני אלשיך אבו אלפרג הזקן היקר בן מר ורב אלשיך אבו אלפכר הזקן היקר<br/>שצ להיות בידיו לראיה כי רציתי ברצון נפשי ובגמ[ר] דעתי ולא אנוס ולא שוגג ולא מוטעה כי אם בדעתי<br/>שלימה ונטלתי וקבלתי שבעה עשר דינרים זהב מצרים מידיו ומכרתי ל[ו] בעדם את רבע הדירה אשר לי בכט<br/>תגיב במצר אלדאכלה פי כוכה אלמעתמד פי אלדאר אלמ/ע/רופה  בסכן סת אלרצא הזקנה היקרה אם [אבו] אלפכר<br/>הנזכר פה מכירה גמורה שלימה וחלוטה גלויה ומפורסמת ממכר שלם אשר לא ישוב והרבע אשר<br/>מכרתי לו בכלל חלקיהם שלשותפים בדירה הזאת שאיע גיר מקסום בעומקא ורומא מתהום ארעא<br/>ועד רום רקיעא בתחתיותיה ועליותיה חדריה וחלונותיה וקירותיה ותקרותיה על ארבעת רבעיה סביב<br/>ימה וקדמה וצפונה ונגבה ומצריה וגבוליה סביב בכל זכיות אשר לד[יר]ה הזאת כאשר כתובהם בשטר<br/>ערבי הנכתב לדירה הזאת ובכללה מכרתי לבני זה אבו אלפרג את הרבע הנזכר בכל זכיות אשר בו ולא שיירתי<br/>לעצמי מן זכות רבע הזה כלום ומהיום הזה והלאה יש לזה אבו אלפרג רשות לעשות ברבע הזה אשר מכרתי<br/>לו כל מה שירצה לבנות בו ולהרוס ולהשכין ולגרש ולהחליף ולמכור ולהוריש ולתת במתנה לכל מי שירצה<br/>ואין מי שימחה בידו וכל מי שיבא מארבע רוחות העולם לערער מכחי אח או אחות קרוב או רחוק ארמ[י<br/>או יהודי יורש נכסי ופורע חובי יהיו דבריו בטלים ושבורים כשבר נבל יוצרים אשר אין לו תקנה ועלי להשתיק<br/>את כל המערער על רבע הדירה הזה הנזכר ולהעמיד הממכר הזה ביד הקונה אותו אנא איקום ואשפה<br/>ואפצה ואדכה ואמרק זביני רבעא דנן אנון ועמליהון ושבחיהון ואוקמינון בידי זבונא וצבי זבונא דנן וקביל<br/>עלוהי וקניוא מן אלשיך אבו אלפכר בכלי הכשר לקנות בו על הממכר הזה וכתבנו בשטר הזה וחתמנו בו<br/>ונתננו לידי אלשיך אבו אלפרג להיות בידיו לראייה וחומר שטר מכירה דנן כחומר כל שטרי מכירת<br/>קרקעות דנהיגי בישראל דלא כאסמכתא ודלא כטופסי דשטרי אלא כחומר וכחוזק כל שטרי מזורזי<br/>ומוחזקי בבי דינא ונהגין ישראל בהון מן קדמת דנא וקנינא מן תרויהון אכל(!) מאי דכתיב ומפרש לעילא<br/>במנא דכשר למקניא ביה בביטול כל מודעי ותנאי בלשון מעכשיו בנפש חפצה ובגמר דעת<br/>עין אלמערופה דתלי ביני שיטי דין קיומה והכל שריר ובריר מהימן וקיים<br/>אביתר הכהן בר אפרים נין  דניאל בר סעדיה . .<br/>יהוסף בית דין כהן צדק זצל  . .</p>"
            },
           "on": "https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586/canvas/1#xywh=0,0,6324,7500"
        }
    ]
}


@click.command()
@with_appcontext
def transcription_iiif():
    # xml_dir = current_app.config['XML_TRANSCRIPTIONS_DIR']
    data_dir = current_app.config['DATA_DIR']
    # TODO: make a subdir for iiif/manifests?

    with open(os.path.join(data_dir, 'transcriptions.json')) as transcriptionsfile:
        transcriptions = json.load(transcriptionsfile)

    solr = SolrClient(current_app.config['SOLR_URL'],
                      current_app.config['SOLR_CORE'])
    # find documents that have a IIIF link that ALSO have transcription
    iiifdocs = SolrQuerySet(solr).filter(iiif_link_s='*', transcription_txt='*')
    print('%d documents' % iiifdocs.count())
    for doc in iiifdocs[:3]:
        print(doc)
        # get the manifest for this document
        response = requests.get(doc['iiif_link_s'])
        if response.status_code != requests.codes.ok:
            print('Error retrieving manifest: %s' % response)
            continue

        manifest = response.json()
        # for now, assume simple structure, single sequence
        # for now, associate the annotation with the first image
        canvas1 = manifest['sequences'][0]['canvases'][0]
        # need id, width, and height
        canvas_id = canvas1['@id']
        canvas_width = canvas1['width']
        canvas_height = canvas1['height']

        annotation_list = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "@id": "http://localhost:8003/coin/canvas/AnnotationList",
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

        # write the new annotation list to a file
        annotation_filename = os.path.join(data_dir, '%s_annotation.json' % doc['id'])
        with open(annotation_filename, 'w') as outfile:
            json.dump(annotation_list, outfile, indent=2)

        # add the annotation to our copy of the manifest
        canvas1['otherContent'] = [
            {
                "@context": "http://iiif.io/api/presentation/2/context.json",
                "@id": annotation_filename,  # FIXME: needs uri?
                "@type": "sc:AnnotationList"
            }
        ]

        manifest_filename = os.path.join(data_dir, '%s_manifest.json' % doc['id'])
        with open(manifest_filename, 'w') as outfile:
            json.dump(manifest, outfile, indent=2)

