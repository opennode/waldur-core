# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.template.defaultfilters import slugify


def init_application_types_slugs(apps, schema_editor):
    ApplicationType = apps.get_model("cost_tracking", "ApplicationType")
    for at in ApplicationType.objects.all():
        at.slug = slugify(at.name)
        at.save()


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0010_applicationtype'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicationtype',
            name='slug',
            field=models.CharField(max_length=150, blank=True),
            preserve_default=True,
        ),
        migrations.RunPython(init_application_types_slugs),
        migrations.AlterField(
            model_name='applicationtype',
            name='slug',
            field=models.CharField(unique=True, max_length=150),
            preserve_default=True,
        ),
    ]
