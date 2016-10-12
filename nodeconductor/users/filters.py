from __future__ import unicode_literals

import django_filters

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
    customer = core_filters.UUIDFilter(
        name='customer_role__customer__uuid',
    )
    customer_url = core_filters.URLFilter(
        view_name='customer-detail',
        name='customer_role__customer__uuid',
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
            'customer',
            'customer_url',
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
