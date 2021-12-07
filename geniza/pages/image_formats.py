from django.utils.html import format_html
from wagtail.images.formats import (
    Format,
    register_image_format,
    unregister_image_format,
)


class CaptionedImageFormat(Format):
    def image_to_html(self, image, alt_text, extra_attributes=None):

        default_html = super().image_to_html(image, alt_text, extra_attributes)

        return format_html(
            "<figure>{}<figcaption>{}</figcaption></figure>", default_html, alt_text
        )


unregister_image_format("fullwidth")
unregister_image_format("left")
unregister_image_format("right")
register_image_format(
    CaptionedImageFormat(
        "captioned_fullwidth", "Full width captioned", "bodytext-image", "width-800"
    )
)
