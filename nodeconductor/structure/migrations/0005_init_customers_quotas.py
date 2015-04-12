# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import migrations
from django.db.models import Q


def init_customers_quotas(apps, schema_editor):
    Customer = apps.get_model('structure', 'Customer')
    Quota = apps.get_model("quotas", 'Quota')
    User = get_user_model()

    customer_ct = ContentType.objects.get_for_model(Customer)

    for customer in Customer.objects.all():
        # projects
        customer_kwargs = {'content_type_id': customer_ct.id, 'object_id': customer.id}
        if not Quota.objects.filter(name='nc_project_count', **customer_kwargs).exists():
            Quota.objects.create(
                uuid=uuid4().hex, name='nc_project_count', usage=customer.projects.count(), **customer_kwargs)

        # users
        if not Quota.objects.filter(name='nc_user_count', **customer_kwargs).exists():
            users_count = (
                User.objects.filter(
                    Q(groups__projectrole__project__customer=customer) |
                    Q(groups__projectgrouprole__project_group__customer=customer) |
                    Q(groups__customerrole__customer=customer))
                .distinct()
                .count()
            )
            Quota.objects.create(
                uuid=uuid4().hex, name='nc_user_count', usage=users_count, **customer_kwargs)


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0004_init_new_quotas'),
    ]

    operations = [
        migrations.RunPython(init_customers_quotas),
    ]
