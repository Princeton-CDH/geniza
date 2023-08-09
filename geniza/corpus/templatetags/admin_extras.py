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
    adminform = list(adminform)
    inlines = list(context["inline_admin_formsets"])

    fieldsets_and_inlines = []
    for choice in getattr(model_admin, "fieldsets_and_inlines_order", ()):
        if choice == "f":
            if adminform:
                fieldsets_and_inlines.append(("f", adminform.pop(0)))
        elif choice == "i":
            if inlines:
                fieldsets_and_inlines.append(("i", inlines.pop(0)))
        elif choice == "itt":
            # special case for itt panel on document
            fieldsets_and_inlines.append(("itt", None))

    # render any remaining ones in the normal order: fieldsets, then inlines
    for fieldset in adminform:
        fieldsets_and_inlines.append(("f", fieldset))
    for inline in inlines:
        fieldsets_and_inlines.append(("i", inline))

    return fieldsets_and_inlines
