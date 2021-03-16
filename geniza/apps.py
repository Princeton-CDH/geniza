from django.contrib.admin.apps import AdminConfig

class GenizaAdminConfig(AdminConfig):
    default_site = 'geniza.admin.GenizaAdminSite'