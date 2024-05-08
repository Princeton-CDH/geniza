from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def next_sort_param(context, sort_field):
    """Get the next sort state in the sequence for a sortable browse view, based
    on the existing sort state for the field specified in the `sort_field` arg,
    as a URL parameter. Used for links in sortable table headers.
    Sequence for sorting: off --> ascending --> descending --> off
    """
    current_sort = context.get("sort", "")
    if sort_field in current_sort:
        # current sort state includes the name of the sort field
        if current_sort.endswith("asc"):
            # ascending: next sort state is descending
            param = "?sort=%s_desc" % sort_field
        else:
            # descending: next sort state is off
            param = "?"
    else:
        # current sort state does not include the name of the sort field,
        # next sort state is ascending
        param = "?sort=%s_asc" % sort_field

    return param
