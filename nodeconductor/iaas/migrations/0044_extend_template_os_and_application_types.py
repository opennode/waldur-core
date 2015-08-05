# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0043_instance_flavor_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='template',
            name='application_type',
            field=models.CharField(default=b'none', help_text='Type of the application inside the template (optional)', max_length=100, blank=True, choices=[(b'wordpress', b'WordPress'), (b'postgresql', b'PostgreSQL'), (b'zimbra', b'Zimbra'), (b'none', b'None')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='template',
            name='os_type',
            field=models.CharField(default=b'other', max_length=10, choices=[(b'centos6', b'Centos 6'), (b'centos7', b'Centos 7'), (b'ubuntu', b'Ubuntu'), (b'rhel6', b'RedHat 6'), (b'rhel7', b'RedHat 7'), (b'freebsd', b'FreeBSD'), (b'windows', b'Windows'), (b'other', b'Other')]),
            preserve_default=True,
        ),
    ]
