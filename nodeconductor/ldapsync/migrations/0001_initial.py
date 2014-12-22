# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LdapToGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ldap_group_name', models.CharField(max_length=80)),
                ('django_group', models.ForeignKey(to='auth.Group')),
            ],
            options={
                'unique_together': set([('ldap_group_name', 'django_group')]),
                'verbose_name': 'LDAP to Django group mapping',
            },
            bases=(models.Model,),
        ),
    ]
