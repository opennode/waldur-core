# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def migrate_application_type_data(apps, schema_editor):
    ApplicationType = apps.get_model('cost_tracking', 'ApplicationType')
    Template = apps.get_model('iaas', 'Template')
    for template in Template.objects.all():
        if template.application_type_old:
            template.application_type = ApplicationType.objects.get(name=template.application_type_old)
            template.save()


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0010_applicationtype'),
        ('iaas', '0046_remove_obsolete_billing_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='template',
            old_name='application_type',
            new_name='application_type_old',
        ),
        migrations.AddField(
            model_name='template',
            name='application_type',
            field=models.ForeignKey(to='cost_tracking.ApplicationType', null=True),
            preserve_default=True,
        ),
        migrations.RunPython(migrate_application_type_data),
        migrations.RemoveField(
            model_name='template',
            name='application_type_old',
        ),
    ]
