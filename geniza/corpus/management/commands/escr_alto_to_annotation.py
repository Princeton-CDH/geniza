import re

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models import Q
from djiffy.models import Canvas, Manifest
from eulxml import xmlmap

from geniza.annotations.models import Annotation
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source, SourceType

# parse eScriptorium ALTO files, generate transcription IIIF annotations,
# and attach to correct documents


class AltoObject(xmlmap.XmlObject):
    # all XmlObjects should inherit this class to get the root namespace
    ROOT_NAMESPACES = {"alto": "http://www.loc.gov/standards/alto/ns-v4#"}


class AltoPolygonalObject(AltoObject):
    polygon = xmlmap.NodeField("alto:Shape/alto:Polygon/@POINTS", AltoObject)


class Line(AltoPolygonalObject):
    content = xmlmap.StringField("alto:String/@CONTENT")


class TextBlock(AltoPolygonalObject):
    id = xmlmap.StringField("./@ID")
    lines = xmlmap.NodeListField("alto:TextLine", Line)
    block_type_id = xmlmap.StringField("./@TAGREFS")


class PrintSpace(AltoObject):
    textblocks = xmlmap.NodeListField("alto:TextBlock", TextBlock)


class Tag(AltoObject):
    id = xmlmap.StringField("./@ID")
    label = xmlmap.StringField("./@LABEL")


class EscriptoriumAlto(AltoObject):
    filename = xmlmap.StringField(
        "//alto:alto/alto:Description/alto:sourceImageInformation/alto:fileName"
    )
    printspace = xmlmap.NodeField(
        "//alto:alto/alto:Layout/alto:Page/alto:PrintSpace", PrintSpace
    )
    tags = xmlmap.NodeListField("//alto:alto/alto:Tags/alto:OtherTag", Tag)


class Command(BaseCommand):
    # regex pattern for image filenames
    filename_pattern = r"PGPID_(?P<pgpid>\d+)_(?P<shelfmark>[\w\-]+)_(?P<img>\d)\..+"

    def add_arguments(self, parser):
        # needs xml filenames as input
        parser.add_argument(
            "alto", metavar="ALTOXML", nargs="+", help="ALTO files to be processed"
        )

    def handle(self, *args, **options):
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        for xmlfile in options["alto"]:
            self.stdout.write("Processing %s" % xmlfile)
            self.ingest_xml(xmlfile)

    def ingest_xml(self, xmlfile):
        alto = xmlmap.load_xmlobject_from_file(xmlfile, EscriptoriumAlto)
        # associate filename with pgpid
        m = re.match(self.filename_pattern, alto.filename)
        pgpid = int(m.group("pgpid"))
        doc = Document.objects.get_by_any_pgpid(pgpid)
        if not doc:
            self.stdout.write("Could not match document; skipping")
            return

        # we should be able to match the shelfmark portion to a manifest short_id
        manifest = self.get_manifest(doc, m.group("shelfmark"))

        # use canvas short_id = img number in sequence
        img_number = int(m.group("img")) + 1
        canvas = self.get_canvas(manifest, img_number)

        if canvas:
            canvas_uri = canvas.uri
        else:
            # create a placeholder canvas URI that contains textblock pk and canvas number
            canvas_base_uri = "%siiif/" % doc.permalink
            b = doc.textblock_set.first()
            canvas_uri = f"{canvas_base_uri}textblock/{b.pk}/canvas/{img_number}/"

        # get scale factor for converting textblock geometry, based on full image width
        img_width = alto.printspace.node.attrib["WIDTH"]
        scale_factor = int(img_width) / (
            canvas.image.image_width if canvas else 640  # placeholder width = 640
        )

        # create annotations
        for tb in alto.printspace.textblocks:
            block_type = None
            if tb.block_type_id:
                # find first tag in tag list whose id matches block type id
                tag_matches = filter(lambda t: t.id == tb.block_type_id, alto.tags)
                tag = next(tag_matches, None)
                if tag:
                    block_type = tag.label
                # TODO: When implementing line-by-line, use block_type to determine rotation

            # skip arabic; these are Hebrew script transcriptions
            if not (block_type and "Arabic" in block_type) and len(tb.lines):
                # get or create footnote
                footnote = self.get_footnote(doc)
                # create annotation and log entry
                anno = Annotation.objects.create(
                    content=self.create_block_annotation(tb, canvas_uri, scale_factor),
                    footnote=footnote,
                )
                LogEntry.objects.log_action(
                    user_id=self.script_user.pk,
                    content_type_id=ContentType.objects.get_for_model(Annotation).pk,
                    object_id=anno.pk,
                    object_repr=str(anno),
                    change_message="Imported from eScriptorium HTR ALTO",
                    action_flag=ADDITION,
                )

    def get_manifest(self, document, short_id):
        """Attempt to get the manifest using the supplied short id; fallback to first manifest,
        or return None if there are none on the document"""
        try:
            # NOTE: this works in 100% of tested files so far!
            return Manifest.objects.get(short_id=short_id)
        except Manifest.DoesNotExist:
            self.stdout.write(
                f"Could not find manifest with short_id {short_id}, falling back to first "
                + "manifest on document"
            )
            manifests = [b.fragment.manifest for b in document.textblock_set.all()]
            # associate with the first manifest
            if manifests and manifests[0]:
                return manifests[0]
            else:
                self.stdout.write(
                    "Could not find manifests on document, falling back to placeholder "
                    + "canvases"
                )
                return None

    def get_canvas(self, manifest, img_number):
        """Attempt to get a canvas from a manifest by id; fallback to first canvas, or return
        None if there are none in the manifest (or there is no manifest)"""
        if manifest and manifest.canvases.exists():
            try:
                return manifest.canvases.get(short_id=str(img_number))
            except Canvas.DoesNotExist:
                self.stdout.write(
                    f"Could not find canvas with short_id {img_number}, falling back to "
                    + "first canvas"
                )
                return manifest.canvases.first()
        else:
            return None

    def get_footnote(self, document):
        """Get or create a digital edition footnote for the HTR transcription"""
        # TODO: Replace this with desired source type and source after decision is made
        (model, _) = SourceType.objects.get_or_create(type="Machine learning model")
        (source, _) = Source.objects.get_or_create(
            title_en="HTR for PGP model 1.0",
            source_type=model,
        )
        try:
            return Footnote.objects.get(
                doc_relation__contains=Footnote.DIGITAL_EDITION,
                source__pk=source.pk,
                content_type=ContentType.objects.get_for_model(Document),
                object_id=document.pk,
            )
        except Footnote.DoesNotExist:
            footnote = Footnote.objects.create(
                content_object=document,
                source=source,
                doc_relation=[Footnote.DIGITAL_EDITION],
            )
            LogEntry.objects.log_action(
                user_id=self.script_user.pk,
                content_type_id=ContentType.objects.get_for_model(Footnote).pk,
                object_id=footnote.pk,
                object_repr=str(footnote),
                change_message="Created new footnote for eScriptorium digital edition",
                action_flag=ADDITION,
            )
            return footnote

    def scale_polygon(self, polygon, scale):
        """Scale points in ALTO polygon by specified scale factor"""
        points = str(polygon).split(" ")
        scaled_points = [round(int(point) / scale, 4) for point in points]
        # return as string for use in svg polygon element
        return " ".join([str(point) for point in scaled_points])

    def create_block_annotation(self, textblock, canvas_uri, scale_factor):
        """Produce a valid IIIF annotation with the block-level content and geometry,
        linked to the IIIF canvas by URI"""

        # lines to HTML list
        block_text = "<ol>\n"
        for line in textblock.lines:
            block_text += f"<li>{line.content}</li>\n"
        block_text += "</ol>"

        # create IIIF annotation
        anno_content = {}
        anno_content["body"] = [
            {
                "TextInput": "rtl",
                "format": "text/html",
                "type": "TextualBody",
                "value": block_text,
            }
        ]
        anno_content["motivation"] = ["sc:supplementing", "transcribing"]
        anno_content["target"] = {
            "source": {
                "id": canvas_uri,
                "type": "Canvas",
            },
        }

        # add selector
        if textblock.polygon:
            # scale polygon points and use SvgSelector
            points = self.scale_polygon(textblock.polygon, scale_factor)
            anno_content["target"]["selector"] = {
                "type": "SvgSelector",
                "value": f'<svg><polygon points="{points}"></polygon></svg>',
            }
        else:
            self.stdout.write(f"No block-level geometry available for {textblock.id}")
            # when no block-level geometry available, use full image FragmentSelector
            anno_content["target"]["selector"] = {
                "conformsTo": "http://www.w3.org/TR/media-frags/",
                "type": "FragmentSelector",
                "value": "xywh=percent:1,1,98,98",
            }

        return anno_content
