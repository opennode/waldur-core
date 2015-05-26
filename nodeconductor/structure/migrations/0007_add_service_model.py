# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('structure', '0006_inherit_namemixin'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('dummy', models.BooleanField(default=False, help_text='Emulate backend operations')),
                ('customer', models.ForeignKey(related_name='services', to='structure.Customer')),
                ('polymorphic_ctype', models.ForeignKey(related_name='polymorphic_structure.service_set+', editable=False, to='contenttypes.ContentType', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='service',
            unique_together=set([('customer', 'name', 'polymorphic_ctype')]),
        ),
    ]
