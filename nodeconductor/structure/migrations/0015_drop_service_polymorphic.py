# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


nc_plus_dependencies = []
if 'nodeconductor_plus.gitlab' in settings.INSTALLED_APPS:
    nc_plus_dependencies.append(
        ('gitlab', '0002_new_service_model'),
    )
if 'nodeconductor_plus.digitalocean' in settings.INSTALLED_APPS:
    nc_plus_dependencies.append(
        ('digitalocean', '0007_new_service_model'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0014_servicesettings_options'),
        ('iaas', '0040_update_cloudprojectmembership'),
        ('oracle', '0003_new_service_model'),
        ('openstack', '0002_new_service_model'),
    ] + nc_plus_dependencies

    operations = [
        migrations.AlterUniqueTogether(
            name='service',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='service',
            name='customer',
        ),
        migrations.RemoveField(
            model_name='service',
            name='polymorphic_ctype',
        ),
        migrations.RemoveField(
            model_name='service',
            name='settings',
        ),
        migrations.DeleteModel(
            name='Service',
        ),
        migrations.RunPython(lambda apps, schema_editor: None),
    ]
