# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0009_floatingip'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='openstackserviceprojectlink',
            unique_together=set([('service', 'project')]),
        ),
    ]
