# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0013_add_creation_state'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='openstackservice',
            options={'verbose_name': 'OpenStack service', 'verbose_name_plural': 'OpenStack services'},
        ),
        migrations.AlterModelOptions(
            name='openstackserviceprojectlink',
            options={'verbose_name': 'OpenStack service project link', 'verbose_name_plural': 'OpenStack service project links'},
        ),
    ]
