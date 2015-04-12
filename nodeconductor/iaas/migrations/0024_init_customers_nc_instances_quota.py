# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.db import migrations
from django.db.models import Count

# Migration cannot rely on constants from the application
# being migrated since at migration time the code potentially
# lack the constant.

# from nodeconductor.structure.quota import RESOURCE_COUNT_QUOTA
RESOURCE_COUNT_QUOTA = 'nc_resource_count'


def init_customers_nc_instances_quota(apps, schema_editor):
    Customer = apps.get_model('structure', 'Customer')
    Quota = apps.get_model('quotas', 'Quota')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    customer_ct = ContentType.objects.get(app_label='structure', model='customer')
    customer_qs = Customer.objects.all()
    customer_qs = customer_qs.annotate(
        instance_count=Count('projects__cloudprojectmembership__instances', distinct=True),
    )

    for customer in customer_qs.iterator():
        Quota.objects.create(
            # We need to add UUID explicitly, because django ignores auto=True parameter in migration UUID field
            uuid=uuid4().hex,
            name=RESOURCE_COUNT_QUOTA,
            content_type=customer_ct,
            object_id=customer.pk,
            usage=customer.instance_count,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0023_add_related_name_to_instance_cpm_field'),
    ]

    operations = [
        migrations.RunPython(init_customers_nc_instances_quota),
    ]
