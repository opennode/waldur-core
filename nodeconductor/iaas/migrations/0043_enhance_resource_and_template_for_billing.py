# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0042_remove_template_fees'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='billing_backend_id',
            field=models.CharField(help_text=b'ID of a resource in backend', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instance',
            name='billing_backend_purchase_order_id',
            field=models.CharField(help_text=b'ID of a purchase order in backend that created a resource', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instance',
            name='billing_backend_template_id',
            field=models.CharField(help_text=b'ID of a template in backend used for creating a resource', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instance',
            name='flavor_name',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
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
