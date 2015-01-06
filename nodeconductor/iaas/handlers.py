from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db import models


def prevent_deletion_of_instances_with_connected_backups(sender, instance, **kwargs):
    from nodeconductor.backup.models import Backup
    ct = ContentType.objects.get_for_model(instance._meta.model)
    connected_backups = Backup.objects.filter(content_type=ct, object_id=instance.id)

    if connected_backups.exists():
        raise models.ProtectedError(
            "Cannot delete some instances of model 'Instance' because "
            "they have connected 'Backups'",
            connected_backups
        )
