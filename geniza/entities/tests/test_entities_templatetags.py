from geniza.entities.templatetags import entities_extras


class TestEntitiesExtrasTemplateTags:
    def test_split(self):
        # template tag wrapper for str.split
        assert entities_extras.split("A,B,C", ",") == ["A", "B", "C"]
