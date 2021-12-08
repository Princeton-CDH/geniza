import pytest
from wagtail.images.formats import Format
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file

from geniza.pages.image_formats import CaptionedImageFormat


class TestCaptionedImageFormat:
    @pytest.mark.django_db
    def test_image_to_html(self):
        cif = CaptionedImageFormat(
            "captioned_fullwidth", "Full width captioned", "bodytext-image", "width-800"
        )
        test_file = get_test_image_file()
        image = Image.objects.create(
            title="Test image",
            file=test_file,
        )
        alt_text = "An example image"
        default_html = Format.image_to_html(cif, image, alt_text)
        html = cif.image_to_html(image, alt_text)
        assert html == "<figure>%s<figcaption>%s</figcaption></figure>" % (
            default_html,
            alt_text,
        )
