# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import migrations


def init_customers_nc_instances_quota(apps, schema_editor):
    Customer = apps.get_model('structure', 'Customer')
    Instance = apps.get_model('iaas', 'Instance')
    Quota = apps.get_model("quotas", 'Quota')

    customer_ct = ContentType.objects.get_for_model(Customer)

    for customer in Customer.objects.all():
        customer_kwargs = {'content_type_id': customer_ct.id, 'object_id': customer.id}
        if not Quota.objects.filter(name='nc-instances', **customer_kwargs).exists():
            instances_count = Instance.objects.filter(cloud_project_membership__project__customer=customer).count()
            Quota.objects.create(
                uuid=uuid4().hex, name='nc-instances', usage=instances_count, **customer_kwargs)


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0022_extend_iaas_template_with_type_icon_name'),
    ]

    operations = [
        migrations.RunPython(init_customers_nc_instances_quota),
    ]
