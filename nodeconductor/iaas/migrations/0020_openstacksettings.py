# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0019_auto_20150310_1341'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpenStackSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('auth_url', models.URLField(help_text='Keystone endpoint url', unique=True)),
                ('username', models.CharField(max_length=100)),
                ('password', models.CharField(max_length=100)),
                ('tenant_name', models.CharField(max_length=100)),
                ('availability_zone', models.CharField(max_length=100, blank=True)),
            ],
            options={
                'verbose_name': 'OpenStack settings',
                'verbose_name_plural': 'OpenStack settings',
            },
            bases=(models.Model,),
        ),
    ]
