# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def init_default_application_types(apps, schema_editor):
    ApplicationType = apps.get_model("cost_tracking", "ApplicationType")
    default_application_types = ('wordpress', 'zimbra', 'postgresql', 'none')
    for name in default_application_types:
        ApplicationType.objects.create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0009_defaultpricelistitem_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.RunPython(init_default_application_types),
    ]
