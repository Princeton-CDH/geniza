"""Signal handlers shared across multiple apps"""


def detach_logentries(sender, instance, **kwargs):
    """Pre-delete signal handler required for models with generic
    relations to log entries.

    To avoid deleting log entries caused by the generic relation
    to log entries, clear out object id for associated log entries
    before deleting the instance."""
    instance.log_entries.update(object_id=None)
