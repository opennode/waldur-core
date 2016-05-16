# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0009_rename_template_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='templategroupresult',
            name='provisioned_resources_data',
            field=jsonfield.fields.JSONField(default=[], help_text='list of provisioned resources data'),
        ),
    ]
