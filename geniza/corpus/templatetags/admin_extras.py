from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def get_fieldsets_and_inlines(context):
    """
    Template tag to render inlines mixed with fieldsets, based on the ModelAdmin's
    fieldsets_and_inlines_order property.
    Adapted from code by Bertrand Bordage: https://github.com/dezede/dezede/commit/ed13cc
    """
    adminform = context["adminform"]
    model_admin = adminform.model_admin
    adminform = iter(adminform)
    inlines = iter(context["inline_admin_formsets"])

    fieldsets_and_inlines = []
    for choice in model_admin.fieldsets_and_inlines_order:
        try:
            if choice == "f":
                fieldsets_and_inlines.append(("f", next(adminform)))
            elif choice == "i":
                fieldsets_and_inlines.append(("i", next(inlines)))
        except StopIteration:
            raise IndexError(
                """Too many values provided to fieldsets_and_inlines_order.
                Ensure there is a fieldset (not just a field) for every 'f' provided."""
            )

    # render any remaining ones in the normal order: fieldsets, then inlines
    for fieldset in adminform:
        fieldsets_and_inlines.append(("f", fieldset))
    for inline in inlines:
        fieldsets_and_inlines.append(("i", inline))

    return fieldsets_and_inlines
