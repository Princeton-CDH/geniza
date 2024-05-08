from geniza.entities.templatetags import entities_extras


class TestEntitiesExtrasTemplateTags:
    def test_next_sort_param(self):
        """Should produce the correct sort params"""
        # not currently sorted by this field --> param should be field_asc
        ctx = {}
        field = "example"
        assert (
            entities_extras.next_sort_param(ctx, sort_field=field)
            == f"?sort={field}_asc"
        )

        # currently sorted by this field asc --> param should be field_desc
        ctx["sort"] = f"{field}_asc"
        assert (
            entities_extras.next_sort_param(ctx, sort_field=field)
            == f"?sort={field}_desc"
        )

        # currently sorted by this field desc --> should remove param
        ctx["sort"] = f"{field}_desc"
        assert entities_extras.next_sort_param(ctx, sort_field=field) == "?"
