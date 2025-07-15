import wagtail.admin.rich_text.editors.draftail.features as draftail_features
from wagtail import hooks
from wagtail.admin.rich_text.converters.html_to_contentstate import (
    InlineStyleElementHandler,
)


@hooks.register("register_rich_text_features")
def register_underline(features):
    """
    Registering the `underline` feature, which uses the `UNDERLINE` Draft.js inline style type,
    and is stored as HTML with a `<mark>` tag (per semantic HTML).
    """

    # Adapted from https://docs.wagtail.org/en/stable/extending/extending_draftail.html

    feature_name = "underline"
    type_ = "UNDERLINE"
    tag = "mark"

    # toolbar configuration
    control = {
        "type": type_,
        "description": "Underline",
        "style": {"textDecoration": "underline"},
    }

    # register the configuration for Draftail
    features.register_editor_plugin(
        "draftail", feature_name, draftail_features.InlineStyleFeature(control)
    )

    # configure the content transform from the DB to the editor and back.
    db_conversion = {
        "from_database_format": {tag: InlineStyleElementHandler(type_)},
        "to_database_format": {
            "style_map": {type_: {"element": tag, "props": {"class": "underline"}}}
        },
    }

    # call register_converter_rule to register the content transformation conversion.
    features.register_converter_rule("contentstate", feature_name, db_conversion)
