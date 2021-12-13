from django.utils.html import format_html
from wagtail.images.formats import (
    Format,
    register_image_format,
    unregister_image_format,
)


class CaptionedImageFormat(Format):
    """Custom image format for including a caption"""

    def image_to_html(self, image, alt_text, extra_attributes=None):
        """Wraps supplied image in figure tags, and supplied alt text in figcaption tags."""
        default_html = super().image_to_html(image, alt_text, extra_attributes)
        class_name = "landscape" if image.width >= image.height else "portrait"

        return format_html(
            '<figure class="{}">{}<figcaption>{}</figcaption></figure>',
            class_name,
            default_html,
            alt_text,
        )


# Unregister Wagtail default image formats
unregister_image_format("fullwidth")
unregister_image_format("left")
unregister_image_format("right")

# Register our custom image format
register_image_format(
    CaptionedImageFormat(
        "captioned_center", "Centered captioned", "bodytext-image", "width-800"
    )
)
