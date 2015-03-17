# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0013_remove_backup_quota'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceStatistics',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(max_length=32)),
                ('value', models.CharField(max_length=255)),
                ('cloud', models.ForeignKey(related_name='stats', to='iaas.Cloud')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
