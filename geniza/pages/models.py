from django.db import models
from django.http.response import HttpResponseRedirect
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
            "underline",
            "link",
            "ol",
            "ul",
            "image",
            "blockquote",
            "superscript",
            "subscript",
            "strikethrough",
        ],
        blank=True,
    )
    # can only be child of Root
    parent_page_types = [Page]
    subpage_types = ["pages.ContentPage", "pages.ContainerPage"]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        RichTextFieldPanel("body"),
    ]

    class Meta:
        verbose_name = "homepage"

    def get_context(self, request):
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
        # redirect to parent page instead
        if self.get_parent():
            return HttpResponseRedirect(self.get_parent().get_url(request))


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
            "underline",
            "link",
            "ol",
            "ul",
            "image",
            "blockquote",
            "superscript",
            "subscript",
            "strikethrough",
        ],
        blank=True,
    )
    # can be child of Home or Container page
    parent_page_types = [HomePage, ContainerPage]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        RichTextFieldPanel("body"),
    ]

    def get_context(self, request):
        context = super(ContentPage, self).get_context(request)
        context["page_type"] = "content-page"
        return context
