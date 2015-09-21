# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import migrations

from nodeconductor.structure.models import Service


def create_quotas(apps, schema_editor):
    Customer = apps.get_model('structure', 'Customer')
    Quota = apps.get_model('quotas', 'Quota')

    customer_ct = ContentType.objects.get_for_model(Customer)
    Quota.objects.filter(name='nc_service_count').update(name='nc_service_project_link_count')

    for customer in Customer.objects.all():
        total = sum(model.objects.filter(customer=customer).count() for model in Service.get_all_models())
        Quota.objects.create(uuid=uuid4().hex,
                             name='nc_service_count',
                             content_type_id=customer_ct.id,
                             object_id=customer.id,
                             usage=total)


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0018_service_settings_plural_form'),
        ('quotas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_quotas),
    ]
