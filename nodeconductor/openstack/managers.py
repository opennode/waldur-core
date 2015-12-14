from django.db import models


class BackupManager(models.Manager):

    def get_queryset(self):
        return super(BackupManager, self).get_queryset().exclude(state=self.model.States.DELETED)

    def get_active(self):
        return super(BackupManager, self).get_queryset().exclude(
            state__in=(self.model.States.DELETING, self.model.States.DELETED, self.model.States.ERRED))
