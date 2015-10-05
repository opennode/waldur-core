# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0008_security_groups'),
    ]

    operations = [
        migrations.CreateModel(
            name='FloatingIP',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('address', models.GenericIPAddressField(protocol=b'IPv4')),
                ('status', models.CharField(max_length=30)),
                ('backend_id', models.CharField(max_length=255)),
                ('backend_network_id', models.CharField(max_length=255, editable=False)),
                ('service_project_link', models.ForeignKey(related_name='floating_ips', to='openstack.OpenStackServiceProjectLink')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='openstackserviceprojectlink',
            name='external_network_id',
            field=models.CharField(max_length=64, blank=True),
            preserve_default=True,
        ),
    ]
