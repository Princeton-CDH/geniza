from django.db import models
from django.http import Http404
from wagtail.admin.edit_handlers import FieldPanel, RichTextFieldPanel
from wagtail.core.fields import RichTextField
from wagtail.core.models import Page


class HomePage(Page):
    """:class:`wagtail.core.models.Page` model for Geniza home page."""

    # fields
    description = models.TextField(blank=True)
    body = RichTextField(
        features=[
            "h2",
            "h3",
            "bold",
            "italic",
            "link",
            "ol",
            "ul",
            "image",
            "embed",
            "blockquote",
            "superscript",
            "subscript",
            "strikethrough",
        ],
        blank=True,
    )
    # can only be child of Root
    parent_page_types = [Page]
    subpage_types = ["pages.ContentPage"]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        RichTextFieldPanel("body"),
    ]

    class Meta:
        verbose_name = "homepage"


class AboutPage(Page):
    """An empty :class:`Page` type that has :class:`ContentPage` instances
    as its subpages."""

    # can only be child of HomePage
    parent_page_types = [HomePage]
    subpage_types = ["pages.ContentPage"]

    # should not ever actually render
    def serve(self, _):
        raise Http404


class ContentPage(Page):
    """A simple :class:`Page` type for content pages."""

    # fields
    description = models.TextField(blank=True)
    body = RichTextField(
        features=[
            "h2",
            "h3",
            "bold",
            "italic",
            "link",
            "ol",
            "ul",
            "image",
            "embed",
            "blockquote",
            "superscript",
            "subscript",
            "strikethrough",
        ],
        blank=True,
    )
    # can be child of Home or About page
    parent_page_types = [HomePage, AboutPage]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        RichTextFieldPanel("body"),
    ]

    def get_context(self, request):
        context = super(ContentPage, self).get_context(request)
        context["page_type"] = "content-page"
        return context
