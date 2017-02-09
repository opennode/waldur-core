# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import migrations, models


def update_users_tokens_lifetime(apps, schema_editor):
    if settings.NODECONDUCTOR['TOKEN_LIFETIME']:
        seconds = settings.NODECONDUCTOR['TOKEN_LIFETIME'].total_seconds()
        User = apps.get_model('core', 'User')
        User.objects.update(
            token_lifetime=int(seconds)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_user_is_support'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='token_lifetime',
            field=models.PositiveIntegerField(help_text='Token lifetime in seconds.', null=True),
        ),
        migrations.RunPython(update_users_tokens_lifetime),
    ]
