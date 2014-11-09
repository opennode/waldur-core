from django.db import models as django_models


class BackupManager(django_models.Manager):

    def get_queryset(self):
        # to avoid circular import:
        from nodeconductor.backup import models
        return super(BackupManager, self).get_queryset().exclude(state=models.Backup.States.DELETED)

    def get_deleted(self):
        return super(BackupManager, self).get_queryset()
