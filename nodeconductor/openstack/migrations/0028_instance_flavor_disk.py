# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def init_flavor_disk(apps, schema_editor):
    Instance = apps.get_model('openstack', 'Instance')
    Flavor = apps.get_model('openstack', 'Flavor')

    for instance in Instance.objects.all():
        settings = instance.service_project_link.service.settings
        flavor = Flavor.objects.filter(name=instance.flavor_name, settings=settings).first()
        if flavor is not None:
            instance.flavor_disk = flavor.disk
        else:
            instance.flavor_disk = instance.system_volume_size
        instance.save()


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0027_instance_image_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='flavor_disk',
            field=models.PositiveIntegerField(default=0, help_text='Flavor disk size in MiB'),
        ),
        migrations.RunPython(init_flavor_disk),
    ]
