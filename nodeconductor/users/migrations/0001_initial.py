# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import nodeconductor.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0037_remove_customer_billing_backend_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invitation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', nodeconductor.core.fields.UUIDField()),
                ('state', models.CharField(default='pending', max_length=8, choices=[('accepted', 'Accepted'), ('canceled', 'Canceled'), ('pending', 'Pending')])),
                ('link_template', models.CharField(help_text='The template must include {uuid} parameter e.g. http://example.com/invitation/{uuid}', max_length=255)),
                ('email', models.EmailField(help_text='Invitation link will be send to this email.', max_length=254)),
                ('project_role', models.ForeignKey(related_name='invitations', to='structure.ProjectRole')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
