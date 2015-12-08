# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0028_servicesettings_service_type2'),
        ('template', '0007_template_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='template',
            name='service_settings',
            field=models.ForeignKey(related_name='templates', to='structure.ServiceSettings', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='template',
            name='order_number',
            field=models.PositiveSmallIntegerField(default=1, help_text=b'Templates in group are sorted by order number. Template with smaller order number will be executed first.', validators=[django.core.validators.MinValueValidator(1)]),
            preserve_default=True,
        ),
    ]
