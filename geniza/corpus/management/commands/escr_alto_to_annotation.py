import re

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from djiffy.models import Canvas, Manifest
from eulxml import xmlmap
from parasolr.django.signals import IndexableSignalHandler

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
    id = xmlmap.StringField("./@ID")
    content = xmlmap.StringField("alto:String/@CONTENT")
    line_type_id = xmlmap.StringField("./@TAGREFS")


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
    # default escr model name
    default_model_name = "HTR for PGP model 1.0"

    # regex pattern for image filenames
    filename_pattern = r"PGPID_(?P<pgpid>\d+)_(?P<shelfmark>[\w\-]+)_(?P<img>\d+)\..+"

    # tags used for rotated blocks and lines
    rotation_tags = [
        "Oblique_45",  # 45°
        "Vertical_Bottom_Up_90",  # 90°
        "Oblique_135",  # 135°
        "Upside_Down",  # 180°
        "Oblique_225",  # 225°
        "Vertical_Top_Down_270",  # 270°
        "Oblique_315",  # 315°
    ]

    # ignore these block types
    bad_block_types = ["Arabic", "Page_Number", "Running_Header"]

    def add_arguments(self, parser):
        # needs xml filenames as input
        parser.add_argument(
            "alto", metavar="ALTOXML", nargs="+", help="ALTO files to be processed"
        )
        parser.add_argument(
            "-b",
            "--block-level",
            action="store_true",
            help="Include this flag if only block-level annotations should be produced (e.g. Weiss ingest)",
        )
        parser.add_argument(
            "-m",
            "--model-name",
            help=f"Optionally supply a custom name for the HTR/OCR model (default: {self.default_model_name})",
            default=self.default_model_name,
        )
        parser.add_argument(
            "-s",
            "--source-id",
            help=f"Optionally supply a custom source ID for the HTR/OCR model",
        )
        parser.add_argument(
            "-n",
            "--new-first",
            action="store_true",
            help="Put the new annotations first on the canvas instead of last, used for re-ingest of missing content.",
        )

    def handle(self, *args, **options):
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # store content type pk for logentry
        self.anno_contenttype = ContentType.objects.get_for_model(Annotation).pk

        # lists for reporting
        self.document_errors = set()
        self.canvas_errors = set()

        # disconnect solr indexing signals; this script will index annotations manually
        IndexableSignalHandler.disconnect()

        # process all files
        for xmlfile in options["alto"]:
            self.stdout.write("Processing %s" % xmlfile)
            self.ingest_xml(
                xmlfile,
                model_name=options["model_name"],
                block_level=options["block_level"],
                source_id=options["source_id"],
                new_first=options["new_first"],
            )

        # report
        self.stdout.write(f"Done! Processed {len(options['alto'])} file(s).")
        if self.document_errors:
            self.stdout.write(
                f"{len(self.document_errors)} file(s) failed to match a PGP document:"
            )
            for filename in self.document_errors:
                self.stdout.write(f"\t- {filename}")
        if self.canvas_errors:
            self.stdout.write(
                f"{len(self.canvas_errors)} file(s) failed to match a specific image. These "
                + "transcriptions have been placed on the first image, or a placeholder if the "
                + "document has no images:"
            )
            for filename in self.canvas_errors:
                self.stdout.write(f"\t- {filename}")

    def ingest_xml(
        self,
        xmlfile,
        model_name=default_model_name,
        block_level=False,
        source_id=None,
        new_first=False,
    ):
        alto = xmlmap.load_xmlobject_from_file(xmlfile, EscriptoriumAlto)
        # associate filename with pgpid
        m = re.match(self.filename_pattern, alto.filename)
        pgpid = int(m.group("pgpid"))
        try:
            doc = Document.objects.get_by_any_pgpid(pgpid)
        except Document.DoesNotExist:
            self.document_errors.add(xmlfile)
            self.stdout.write("Could not match document; skipping")
            return

        # we should be able to match the shelfmark portion to a manifest short_id
        manifest = self.get_manifest(doc, m.group("shelfmark"), xmlfile)

        # use canvas short_id = img number in sequence
        img_number = int(m.group("img")) + 1
        canvas = self.get_canvas(manifest, img_number, xmlfile)

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
        new_anno_pks = []
        footnote = None
        for tb_idx, tb in enumerate(alto.printspace.textblocks, start=1):
            block_type = None
            if tb.block_type_id:
                # find first tag in tag list whose id matches block type id
                tag_matches = filter(lambda t: t.id == tb.block_type_id, alto.tags)
                tag = next(tag_matches, None)
                if tag:
                    block_type = tag.label

            # skip arabic; these are Hebrew script transcriptions
            if not (
                block_type and any(t in block_type for t in self.bad_block_types)
            ) and len(tb.lines):
                # get or create footnote
                footnote = self.get_footnote(doc, model_name, source_id)
                # create annotation and log entry
                block = Annotation.objects.create(
                    content=self.create_block_annotation(
                        tb,
                        canvas_uri,
                        scale_factor,
                        block_type,
                        tb_idx,
                        include_content=block_level,
                    ),
                    footnote=footnote,
                )
                new_anno_pks.append(block.pk)
                LogEntry.objects.log_action(
                    user_id=self.script_user.pk,
                    content_type_id=self.anno_contenttype,
                    object_id=block.pk,
                    object_repr=str(block),
                    change_message="Imported block from eScriptorium HTR ALTO",
                    action_flag=ADDITION,
                )

                # create line annotations from lines and link to block
                if not block_level:
                    for i, line in enumerate(tb.lines, start=1):
                        line_type = None
                        if line.line_type_id:
                            # find first tag in tag list whose id matches line type id
                            tag_matches = filter(
                                lambda t: t.id == line.line_type_id, alto.tags
                            )
                            tag = next(tag_matches, None)
                            if tag:
                                line_type = tag
                        line_anno = Annotation.objects.create(
                            content=self.create_line_annotation(
                                line, block, scale_factor, line_type, order=i
                            ),
                            block=block,
                            footnote=footnote,
                        )
                        LogEntry.objects.log_action(
                            user_id=self.script_user.pk,
                            content_type_id=self.anno_contenttype,
                            object_id=line_anno.pk,
                            object_repr=str(line_anno),
                            change_message="Imported line from eScriptorium HTR ALTO",
                            action_flag=ADDITION,
                        )
        if new_first and footnote:
            # get existing annotations on this footnote + canvas to reorder them
            existing_annos = (
                Annotation.objects.filter(
                    footnote=footnote,
                    content__target__source__id=canvas_uri,
                )
                .exclude(pk__in=new_anno_pks)
                .order_by("content__schema:position", "created")
            )
            # move existing annotations to the end so that new ones are first
            for new_idx, anno in enumerate(existing_annos, start=1):
                anno.content["schema:position"] = tb_idx + new_idx
                anno.save()

        # index after all blocks added
        doc.index()

    def get_manifest(self, document, short_id, filename):
        """Attempt to get the manifest using the supplied short id; fallback to first manifest,
        or return None if there are none on the document"""
        try:
            # NOTE: this works in 100% of tested files so far!
            return Manifest.objects.get(short_id=short_id)
        except Manifest.DoesNotExist:
            self.canvas_errors.add(filename)
            manifests = [b.fragment.manifest for b in document.textblock_set.all()]
            # associate with the first manifest
            if manifests and manifests[0]:
                self.stdout.write(
                    f"Could not find manifest with short_id {short_id}, falling back to first "
                    + f"manifest on document (of {len(manifests)})"
                )
                return manifests[0]
            else:
                self.stdout.write(
                    "Could not find manifests on document, falling back to placeholder canvases"
                )
                return None

    def get_canvas(self, manifest, img_number, filename):
        """Attempt to get a canvas from a manifest by id; fallback to first canvas, or return
        None if there are none in the manifest (or there is no manifest)"""
        if manifest and manifest.canvases.exists():
            try:
                return manifest.canvases.get(short_id=str(img_number))
            except Canvas.DoesNotExist:
                self.canvas_errors.add(filename)
                self.stdout.write(
                    f"Could not find canvas with short_id {img_number}, falling back to "
                    + "first canvas"
                )
                return manifest.canvases.first()
        else:
            return None

    def get_footnote(self, document, model_name=default_model_name, source_id=None):
        """Get or create a digital edition footnote for the HTR transcription"""
        if source_id:
            # this command should actually error on Source.DoesNotExist in this case
            source = Source.objects.get(pk=int(source_id))
        else:
            # TODO: Replace this with desired source type and source after decision is made
            (model, _) = SourceType.objects.get_or_create(type="Machine learning model")
            (source, _) = Source.objects.get_or_create(
                title_en=model_name,
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

    def create_block_annotation(
        self,
        textblock,
        canvas_uri,
        scale_factor,
        block_type,
        order,
        include_content=False,
    ):
        """Produce a valid IIIF annotation with the block-level content and geometry,
        linked to the IIIF canvas by URI"""

        # create IIIF annotation
        anno_content = {}
        anno_content["schema:position"] = order
        anno_content["textGranularity"] = "block"
        anno_content["motivation"] = ["sc:supplementing", "transcribing"]
        anno_content["target"] = {
            "source": {
                "id": canvas_uri,
                "type": "Canvas",
            },
        }
        if include_content:
            # lines to HTML list
            block_text = "<ol>\n"
            for line in textblock.lines:
                block_text += f"<li>{line.content}</li>\n"
            block_text += "</ol>"
            # include HTML list as content if we're producing only block-level
            anno_content["body"] = [
                {
                    "TextInput": "rtl",
                    "format": "text/html",
                    "type": "TextualBody",
                    "value": block_text,
                }
            ]
        if block_type:
            if "body" in anno_content:
                anno_content["body"][0]["label"] = block_type
            else:
                anno_content["body"] = [
                    {
                        "label": block_type,
                    }
                ]
            if block_type in self.rotation_tags:
                # add rotation tag as a CSS class to this block
                anno_content["target"]["styleClass"] = block_type

        # add selector
        if textblock.polygon and not include_content:
            # scale polygon points and use SvgSelector
            points = self.scale_polygon(textblock.polygon, scale_factor)
            anno_content["target"]["selector"] = {
                "type": "SvgSelector",
                "value": f'<svg><polygon points="{points}"></polygon></svg>',
            }
        else:
            if not textblock.polygon:
                self.stdout.write(
                    f"No block-level geometry available for {textblock.id}"
                )
            # if no block-level geometry available, or this is Weiss, use
            # full image FragmentSelector
            anno_content["target"]["selector"] = {
                "conformsTo": "http://www.w3.org/TR/media-frags/",
                "type": "FragmentSelector",
                "value": "xywh=percent:1,1,98,98",
            }

        return anno_content

    def create_line_annotation(self, line, block_anno, scale_factor, line_type, order):
        # create IIIF annotation
        anno_content = {}
        anno_content["schema:position"] = order
        anno_content["body"] = [
            {
                "TextInput": "rtl",
                "format": "text/html",
                "type": "TextualBody",
                "value": line.content,
            }
        ]
        anno_content["textGranularity"] = "line"
        anno_content["motivation"] = block_anno.content["motivation"]
        anno_content["target"] = {"source": block_anno.content["target"]["source"]}
        if line_type and line_type in self.rotation_tags:
            # add rotation tag as a CSS class to this line (sometimes differs from block)
            anno_content["target"]["styleClass"] = line_type
        elif "styleClass" in block_anno.content["target"]:
            # if block has rotation but line doesn't, use block's rotation
            anno_content["target"]["styleClass"] = block_anno.content["target"][
                "styleClass"
            ]

        # add selector
        if line.polygon:
            # scale polygon points and use SvgSelector
            points = self.scale_polygon(line.polygon, scale_factor)
            anno_content["target"]["selector"] = {
                "type": "SvgSelector",
                "value": f'<svg><polygon points="{points}"></polygon></svg>',
            }
        else:
            self.stdout.write(f"No line-level geometry available for {line.id}")

        return anno_content
