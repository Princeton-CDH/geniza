from django.contrib import admin

from geniza.people.models import Person

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('sort_name',)
    search_fields = ('sort_name',)
