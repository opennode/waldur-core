
def add_quotas_to_owner(sender, instance, created=False, **kwargs):
    if created:
        from nodeconductor.quotas import models
        for quota_name in sender.QUOTAS_NAMES:
            models.Quota.objects.create(name=quota_name, owner=instance)
