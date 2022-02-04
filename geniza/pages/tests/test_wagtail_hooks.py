from unittest.mock import MagicMock

from geniza.pages.wagtail_hooks import register_underline


def test_register_underline():
    mock_features = MagicMock()
    register_underline(mock_features)
    mock_features.register_editor_plugin.assert_called
    mock_features.register_converter_rule.assert_called
