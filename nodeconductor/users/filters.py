from __future__ import unicode_literals

import uuid

import django_filters
from django.db.models import Q
from rest_framework.filters import DjangoFilterBackend

from nodeconductor.core import filters as core_filters
from nodeconductor.structure import models as structure_models
from nodeconductor.users import models


class InvitationFilter(django_filters.FilterSet):
    project = core_filters.UUIDFilter(
        name='project_role__project__uuid',
    )
    project_url = core_filters.URLFilter(
        view_name='project-detail',
        name='project_role__project__uuid',
    )
    project_role = core_filters.MappedChoiceFilter(
        name='project_role__role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
            # TODO: Removing this drops support of filtering by numeric codes
            (structure_models.ProjectRole.ADMINISTRATOR, 'Administrator'),
            (structure_models.ProjectRole.MANAGER, 'Manager'),
        ),
        choice_mappings={
            'admin': structure_models.ProjectRole.ADMINISTRATOR,
            'manager': structure_models.ProjectRole.MANAGER,
        },
    )
    customer_role = core_filters.MappedChoiceFilter(
        name='customer_role__role_type',
        choices=(
            ('owner', 'Owner'),
            # TODO: Removing this drops support of filtering by numeric codes
            (structure_models.CustomerRole.OWNER, 'Owner'),
        ),
        choice_mappings={
            'owner': structure_models.CustomerRole.OWNER,
        },
    )

    class Meta(object):
        model = models.Invitation
        fields = [
            'email',
            'state',
            'customer_role',
            'project',
            'project_url',
            'project_role',
        ]
        order_by = [
            'email',
            'state',
            # desc
            '-email',
            '-state',
        ]


class InvitationCustomerFilterBackend(DjangoFilterBackend):
    url_filter = core_filters.URLFilter(
        view_name='customer-detail',
        name='customer_role__customer__uuid',
    )

    def filter_queryset(self, request, queryset, view):
        customer_uuid = self.extract_customer_uuid(request)
        if not customer_uuid:
            return queryset

        try:
            uuid.UUID(customer_uuid)
        except ValueError:
            return queryset.none()

        query = Q(customer_role__customer__uuid=customer_uuid)
        query |= Q(project_role__project__customer__uuid=customer_uuid)
        return queryset.filter(query)

    def extract_customer_uuid(self, request):
        if 'customer_url' in request.query_params:
            return self.url_filter.get_uuid(request.query_params['customer_url'])

        if 'customer' in request.query_params:
            return request.query_params['customer']
