# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0038_auto_20161228_1048'),
        ('users', '0004_auto_20161228_1048'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(
            name='CustomerRole',
        ),
        migrations.DeleteModel(
            name='ProjectGroup',
        ),
        migrations.DeleteModel(
            name='ProjectGroupRole',
        ),
        migrations.DeleteModel(
            name='ProjectRole',
        ),
        migrations.AddField(
            model_name='projectpermission',
            name='created_by',
            field=models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AddField(
            model_name='projectpermission',
            name='project',
            field=models.ForeignKey(related_name='permissions', to='structure.Project'),
        ),
        migrations.AddField(
            model_name='projectpermission',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='customerpermission',
            name='created_by',
            field=models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AddField(
            model_name='customerpermission',
            name='customer',
            field=models.ForeignKey(related_name='permissions', to='structure.Customer'),
        ),
        migrations.AddField(
            model_name='customerpermission',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='projectpermission',
            unique_together=set([('project', 'role', 'user', 'is_active')]),
        ),
        migrations.AlterUniqueTogether(
            name='customerpermission',
            unique_together=set([('customer', 'role', 'user', 'is_active')]),
        ),
    ]
