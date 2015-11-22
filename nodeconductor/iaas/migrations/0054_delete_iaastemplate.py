# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0053_resource_error_message'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='flavor',
        ),
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='project',
        ),
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='template',
        ),
        migrations.RemoveField(
            model_name='iaastemplateservice',
            name='templateservice_ptr',
        ),
        migrations.DeleteModel(
            name='IaasTemplateService',
        ),
    ]
