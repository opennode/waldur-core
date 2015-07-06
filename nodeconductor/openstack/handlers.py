

# TODO: Consider removing this handler and apply defaults directly during provisioning (NC-632)
def set_spl_default_availability_zone(sender, instance=None, **kwargs):
    if not instance.availability_zone:
        settings = instance.service.settings
        instance.availability_zone = settings.options['availability_zone']
