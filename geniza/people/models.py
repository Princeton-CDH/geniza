from django.db import models

class Person(models.Model):
    # both first and last name are optional, just stubbing for now
    last_name = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return ' '.join([self.first_name or '', self.last_name or ''])

    class Meta:
        verbose_name_plural = 'people'
        # TODO: Are names unique? I'd imagine people share names but are different 
        #  people? How does PGP distinguish between these?
        # constraints = [
        #     models.UniqueConstraint(fields=['first_name', 'last_name'],
        #                             name='unique_full_name')
        # ]