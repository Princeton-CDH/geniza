from django.db import models
from django.http.response import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from wagtail.admin.edit_handlers import FieldPanel, StreamFieldPanel
from wagtail.core import blocks
from wagtail.core.fields import StreamField
from wagtail.core.models import Page
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.images.blocks import ImageChooserBlock

# Translators: help text for image alternative text
ALT_TEXT_HELP = _(
    """Alternative text for visually impaired users to
briefly communicate the intended message of the image in this context."""
)


class CaptionedImageBlock(blocks.StructBlock):
    """:class:`~wagtail.core.blocks.StructBlock` for an image with
    alternative text and optional formatted caption, so
    that both caption and alternative text can be context-specific."""

    # Adapted from mep-django

    image = ImageChooserBlock()
    alternative_text = blocks.TextBlock(required=True, help_text=ALT_TEXT_HELP)
    caption = blocks.RichTextBlock(
        features=["link", "superscript"],
        required=False,
    )

    class Meta:
        icon = "image"
        template = "pages/blocks/captioned_image_block.html"


class SVGImageBlock(blocks.StructBlock):
    """:class:`~wagtail.core.blocks.StructBlock` for an SVG image with
    alternative text and optional formatted caption. Separate from
    :class:`CaptionedImageBlock` because Wagtail image handling
    does not work with SVG."""

    extended_description_help = _(
        """This text will only be read to \
    non-sighted users and should describe the major insights or \
    takeaways from the graphic. Multiple paragraphs are allowed."""
    )

    # Adapted from mep-django

    image = DocumentChooserBlock()
    alternative_text = blocks.TextBlock(required=True, help_text=ALT_TEXT_HELP)
    caption = blocks.RichTextBlock(
        features=["link", "superscript"],
        required=False,
    )
    extended_description = blocks.RichTextBlock(
        features=["p"], required=False, help_text=extended_description_help
    )

    class Meta:
        icon = "image"
        label = "SVG"
        template = "pages/blocks/svg_image_block.html"


class AccordionBlock(blocks.StructBlock):
    """Accordion :class:`~wagtail.core.blocks.StructBlock` for collapsible
    sections and/or FAQs"""

    label = blocks.CharBlock(label="Heading label/question", required=True)
    content = blocks.RichTextBlock(
        label="Expanded details/answer",
        features=[
            "bold",
            "italic",
            "underline",
            "link",
            "ol",
            "ul",
            "blockquote",
            "superscript",
            "subscript",
            "strikethrough",
        ],
        required=True,
    )

    class Meta:
        icon = "folder-open-1"
        template = "pages/blocks/accordion_block.html"
        label = "Collapsible paragraph (accordion)"


class BodyContentBlock(blocks.StreamBlock):
    """Common set of content blocks for content pages."""

    # Adapted from mep-django

    # fields
    paragraph = blocks.RichTextBlock(
        features=[
            "h2",
            "h3",
            "bold",
            "italic",
            "underline",
            "link",
            "ol",
            "ul",
            "blockquote",
            "superscript",
            "subscript",
            "strikethrough",
        ],
        required=False,
    )
    collapsible_paragraph = AccordionBlock()
    image = CaptionedImageBlock()
    svg_image = SVGImageBlock()


class HomePage(Page):
    """:class:`wagtail.core.models.Page` model for Geniza home page."""

    # fields
    description = models.TextField(blank=True)
    body = StreamField(BodyContentBlock)
    # can only be child of Root
    parent_page_types = [Page]
    subpage_types = ["pages.ContentPage", "pages.ContainerPage"]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        StreamFieldPanel("body"),
    ]

    class Meta:
        verbose_name = "homepage"

    def get_context(self, request):
        """add page type to context"""
        context = super(HomePage, self).get_context(request)
        context["page_type"] = "homepage"
        return context


class ContainerPage(Page):
    """An empty :class:`Page` type that has :class:`ContentPage` instances
    as its subpages."""

    # can only be child of HomePage
    parent_page_types = [HomePage]
    subpage_types = ["pages.ContentPage"]

    # show in menu by default
    show_in_menus_default = True

    # should not ever actually render
    def serve(self, request):
        """override serve method to redirect to parent page instead of rendering"""
        if self.get_parent():
            return HttpResponseRedirect(self.get_parent().get_url(request))


class ContentPage(Page):
    """A simple :class:`Page` type for content pages."""

    # fields
    description = models.TextField(blank=True)
    body = StreamField(BodyContentBlock)
    # can be child of Home or Container page
    parent_page_types = [HomePage, ContainerPage]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        StreamFieldPanel("body"),
    ]

    # show in menu by default
    show_in_menus_default = True

    def get_context(self, request):
        """add page type to context"""
        context = super(ContentPage, self).get_context(request)
        context["page_type"] = "content-page"
        return context
