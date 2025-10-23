from django.db import models


class Manual(models.Model):
    """Model for storing quick links to training materials, manuals, and other resources in the admin"""

    name = models.CharField(max_length=255, blank=False)
    url = models.URLField("URL", blank=False)
