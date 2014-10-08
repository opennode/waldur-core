# list of models that support backing up
# each app.model provides backup strategy that implements model-specific backup algorithm

from django.db import models


BACKUP_REGISTRY = {
    'Instance': 'iaas_instance'
}


def get_backupable_models():
    """
    Gets list of backupable models classes
    """
    backupable_models = []
    for model_code in BACKUP_REGISTRY.itervalues():
        app_label, model_name = model_code.split('_')
        backupable_models.append(models.get_model(app_label, model_name))
        return backupable_models
