from django.db import models as django_models


class BackupManager(django_models.Manager):

    def get_queryset(self):
        return super(BackupManager, self).get_queryset().exclude(state=self.model.States.DELETED)

    def get_active(self):
        return super(BackupManager, self).get_queryset().exclude(
            state__in=(self.model.States.DELETING, self.model.States.DELETED, self.model.States.ERRED))

    def get_deleted(self):
        return super(BackupManager, self).get_queryset()
