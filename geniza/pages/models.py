from django.db import models
from modeltranslation.manager import MultilingualManager
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
    subpage_types = ["pages.ContentPage", "pages.CreditsPage"]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        RichTextFieldPanel("body"),
    ]

    class Meta:
        verbose_name = "homepage"


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
    parent_page_types = [HomePage]
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        RichTextFieldPanel("body"),
    ]

    def get_context(self, request):
        context = super(ContentPage, self).get_context(request)
        context["page_type"] = "content-page"
        return context


class ContributorManager(MultilingualManager):
    def get_by_natural_key(self, last_name, first_name):
        return self.get(last_name=last_name, first_name=first_name)


class Contributor(models.Model):
    """Contributor to be listed on the credits page"""

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    role = models.CharField(max_length=255)

    objects = ContributorManager()

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["first_name", "last_name"], name="contributor_unique_name"
            )
        ]

    def __str__(self):
        """Creator full name, with first name first"""
        return " ".join([n for n in [self.first_name, self.last_name] if n])

    def natural_key(self):
        return (self.last_name, self.first_name)


class CreditsPage(ContentPage):
    """:class:`ContentPage` model for displaying a credits page."""

    content_panels = Page.content_panels + [
        FieldPanel("description"),
    ]

    def contributors(self):
        return Contributor.objects.all()
