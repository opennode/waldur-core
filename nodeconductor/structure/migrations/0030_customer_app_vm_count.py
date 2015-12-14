# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import defaultdict
from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import migrations
from django.db.models import Count

from nodeconductor.structure.models import Service, Resource


def get_resources_count(resource_models):
    counts = defaultdict(lambda: 0)
    for model in resource_models:
        customer_path = model.Permissions.customer_path
        rows = model.objects.values(customer_path).annotate(count=Count('id'))
        for row in rows:
            customer_id = row[customer_path]
            counts[customer_id] += row['count']
    return counts


def create_quotas(apps, schema_editor):
    Customer = apps.get_model('structure', 'Customer')
    Quota = apps.get_model('quotas', 'Quota')

    customer_ct = ContentType.objects.get_for_model(Customer)
    customer_vms = get_resources_count(Resource.get_vm_models())
    customer_apps = get_resources_count(Resource.get_app_models())

    for customer in Customer.objects.all():
        Quota.objects.create(uuid=uuid4().hex,
                             name='nc_vm_count',
                             content_type_id=customer_ct.id,
                             object_id=customer.id,
                             usage=customer_vms.get(customer.id, 0))

        Quota.objects.create(uuid=uuid4().hex,
                             name='nc_app_count',
                             content_type_id=customer_ct.id,
                             object_id=customer.id,
                             usage=customer_apps.get(customer.id, 0))


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0029_project_app_vm_count'),
        ('quotas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_quotas),
    ]
