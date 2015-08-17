from __future__ import unicode_literals

import time
import logging
import functools
import StringIO
import django_filters

from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta

from django import http
from django.conf import settings as django_settings
from django.contrib import auth
from django.db import connection, transaction, IntegrityError
from django.db.models import Q, Sum
from django.template.loader import render_to_string
from django.utils import timezone
from django_fsm import TransitionNotAllowed
from xhtml2pdf import pisa

from rest_framework import filters as rf_filters
from rest_framework import mixins
from rest_framework import permissions as rf_permissions
from rest_framework import serializers as rf_serializers
from rest_framework import status
from rest_framework import views
from rest_framework import viewsets
from rest_framework import generics
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed, APIException
from rest_framework.response import Response

from nodeconductor.core import filters as core_filters
from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import exceptions as core_exceptions
from nodeconductor.core import utils as core_utils
from nodeconductor.core.tasks import send_task
from nodeconductor.core.utils import request_api
from nodeconductor.quotas import views as quotas_views
from nodeconductor.structure import SupportedServices, ServiceBackendError, ServiceBackendNotImplemented
from nodeconductor.structure import filters
from nodeconductor.structure import permissions
from nodeconductor.structure import models
from nodeconductor.structure import serializers
from nodeconductor.structure.log import event_logger


logger = logging.getLogger(__name__)

User = auth.get_user_model()


class CustomerFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        lookup_type='icontains',
    )
    abbreviation = django_filters.CharFilter(
        lookup_type='icontains',
    )
    contact_details = django_filters.CharFilter(
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.Customer
        fields = [
            'name',
            'abbreviation',
            'contact_details',
            'native_name',
            'registration_code',
        ]
        order_by = [
            'name',
            'abbreviation',
            'contact_details',
            'native_name',
            'registration_code',
            # desc
            '-name',
            '-abbreviation',
            '-contact_details',
            '-native_name',
            '-registration_code',
        ]


class CustomerViewSet(viewsets.ModelViewSet):
    """List of customers that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#customer-management
    """

    queryset = models.Customer.objects.all()
    serializer_class = serializers.CustomerSerializer
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend,)
    filter_class = CustomerFilter

    def perform_create(self, serializer):
        customer = serializer.save()
        if not self.request.user.is_staff:
            customer.add_user(self.request.user, models.CustomerRole.OWNER)

    # XXX: This detail route should be moved to billing application.
    @list_route()
    def annual_report(self, request):
        from nodeconductor.billing.models import Invoice

        group_by = request.query_params.get('group_by', 'customer')
        if group_by not in ('customer', 'month'):
            return Response(
                {'Detail': 'group_by parameter can be only `month` or `customer`'},
                status=status.HTTP_400_BAD_REQUEST)

        year_ago = timezone.now().replace(day=1) - timedelta(days=365)
        truncate_date = connection.ops.date_trunc_sql('month', 'date')
        invoices = Invoice.objects.filter(date__gte=year_ago)
        invoices_values = (
            invoices
            .extra({'month': truncate_date})
            .values('month', 'customer__name')
            .annotate(Sum('amount'))
        )

        formatted_data = defaultdict(list)
        if group_by == 'customer':
            for invoice in invoices_values:
                month = invoice['month']
                if isinstance(month, basestring):
                    month = datetime.strptime(invoice['month'], '%Y-%m-%d')
                formatted_data[invoice['customer__name']].append((month, invoice['amount__sum']))
            formatted_data.default_factory = None
            for customer_name, month_data in formatted_data.items():
                formatted_data[customer_name] = sorted(month_data, key=lambda x: x[0])
        else:
            for invoice in invoices_values:
                month = invoice['month']
                if isinstance(month, basestring):
                    month = datetime.strptime(invoice['month'], '%Y-%m-%d')
                formatted_data[month].append((invoice['customer__name'], invoice['amount__sum']))
            formatted_data.default_factory = None

        formatted_data = OrderedDict(sorted(formatted_data.items(), key=lambda x: x[0]))
        partial_sums = [sum([el[1] for el in v]) for v in formatted_data.values()]
        total_sum = sum(partial_sums)

        context = {
            'formatted_data': formatted_data,
            'group_by': group_by,
            'partial_sums': iter(partial_sums),
            'total_sum': total_sum
        }

        result = StringIO.StringIO()
        pisa.pisaDocument(
            StringIO.StringIO(render_to_string('billing/annual_report.html', context)),
            result
        )

        response = http.HttpResponse(result.getvalue(), content_type='application/pdf')

        if request.query_params.get('download'):
            response['Content-Disposition'] = 'attachment; filename="annual_report.pdf"'

        return response


class CustomerImageView(generics.UpdateAPIView, generics.DestroyAPIView):

    queryset = models.Customer.objects.all()
    lookup_field = 'uuid'
    serializer_class = serializers.CustomerImageSerializer

    def perform_destroy(self, instance):
        instance.image = None
        instance.save()

    def check_object_permissions(self, request, customer):
        if request.user.is_staff:
            return
        if customer.has_user(request.user, models.CustomerRole.OWNER):
            return
        raise PermissionDenied()


class ProjectFilter(quotas_views.QuotaFilterMixin, django_filters.FilterSet):
    customer = django_filters.CharFilter(
        name='customer__uuid',
        distinct=True,
    )

    customer_name = django_filters.CharFilter(
        name='customer__name',
        distinct=True,
        lookup_type='icontains'
    )

    customer_native_name = django_filters.CharFilter(
        name='customer__native_name',
        distinct=True,
        lookup_type='icontains'
    )

    customer_abbreviation = django_filters.CharFilter(
        name='customer__abbreviation',
        distinct=True,
        lookup_type='icontains'
    )

    project_group = django_filters.CharFilter(
        name='project_groups__uuid',
        distinct=True,
    )

    project_group_name = django_filters.CharFilter(
        name='project_groups__name',
        distinct=True,
        lookup_type='icontains'
    )

    name = django_filters.CharFilter(lookup_type='icontains')

    description = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = models.Project
        fields = [
            'project_group',
            'project_group_name',
            'name',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'description',
            'created',
        ]
        order_by = [
            'name',
            '-name',
            'created',
            '-created',
            'project_groups__name',
            '-project_groups__name',
            'customer__native_name',
            '-customer__native_name',
            'customer__name',
            '-customer__name',
            'customer__abbreviation',
            '-customer__abbreviation',
        ]

        order_by_mapping = {
            # Proper field naming
            'project_group_name': 'project_groups__name',
            'customer_name': 'customer__name',
            'customer_abbreviation': 'customer__abbreviation',
            'customer_native_name': 'customer__native_name',

            # Backwards compatibility
            'project_groups__name': 'project_groups__name',
        }


class ProjectViewSet(viewsets.ModelViewSet):
    """List of projects that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#project-management
    """

    queryset = models.Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, core_filters.DjangoMappingFilterBackend)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)
    filter_class = ProjectFilter

    def can_create_project_with(self, customer, project_groups):
        user = self.request.user

        if user.is_staff:
            return True

        if customer.has_user(user, models.CustomerRole.OWNER):
            return True

        if project_groups and all(
                project_group.has_user(user, models.ProjectGroupRole.MANAGER)
                for project_group in project_groups
        ):
            return True

        return False

    def get_queryset(self):
        user = self.request.user
        queryset = super(ProjectViewSet, self).get_queryset()

        can_manage = self.request.query_params.get('can_manage', None)
        if can_manage is not None:
            queryset = queryset.filter(
                Q(customer__roles__permission_group__user=user,
                  customer__roles__role_type=models.CustomerRole.OWNER)
                |
                Q(roles__permission_group__user=user,
                  roles__role_type=models.ProjectRole.MANAGER)
            ).distinct()

        can_admin = self.request.query_params.get('can_admin', None)

        if can_admin is not None:
            queryset = queryset.filter(
                roles__permission_group__user=user,
                roles__role_type=models.ProjectRole.ADMINISTRATOR,
            )

        return queryset

    def perform_create(self, serializer):
        customer = serializer.validated_data['customer']
        project_groups = serializer.validated_data['project_groups']

        if not self.can_create_project_with(customer, project_groups):
            raise PermissionDenied('You do not have permission to perform this action.')

        customer.validate_quota_change({'nc_project_count': 1}, raise_exception=True)

        super(ProjectViewSet, self).perform_create(serializer)


class ProjectGroupFilter(django_filters.FilterSet):
    customer = django_filters.CharFilter(
        name='customer__uuid',
        distinct=True,
    )
    customer_name = django_filters.CharFilter(
        name='customer__name',
        distinct=True,
        lookup_type='icontains',
    )
    customer_native_name = django_filters.CharFilter(
        name='customer__native_name',
        distinct=True,
        lookup_type='icontains',
    )

    customer_abbreviation = django_filters.CharFilter(
        name='customer__abbreviation',
        distinct=True,
        lookup_type='icontains',
    )

    name = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = models.ProjectGroup
        fields = [
            'name',
            'customer',
            'customer_name',
            'customer_native_name',
            'customer_abbreviation',
        ]
        order_by = [
            'name',
            '-name',
            'customer__name',
            '-customer__name',
            'customer__native_name',
            '-customer__native_name',
            'customer__abbreviation',
            '-customer__abbreviation',
        ]
        order_by_mapping = {
            'customer_name': 'customer__name',
            'customer_abbreviation': 'customer__abbreviation',
            'customer_native_name': 'customer__native_name',
        }


class ProjectGroupViewSet(viewsets.ModelViewSet):
    """
    List of project groups that are accessible to this user.
    """

    queryset = models.ProjectGroup.objects.all()
    serializer_class = serializers.ProjectGroupSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, core_filters.DjangoMappingFilterBackend)
    # permission_classes = (permissions.IsAuthenticated,)  # TODO: Add permissions for Create/Update
    filter_class = ProjectGroupFilter


class ProjectGroupMembershipFilter(django_filters.FilterSet):
    project_group = django_filters.CharFilter(
        name='projectgroup__uuid',
    )

    project_group_name = django_filters.CharFilter(
        name='projectgroup__name',
        lookup_type='icontains',
    )

    project = django_filters.CharFilter(
        name='project__uuid',
    )

    project_name = django_filters.CharFilter(
        name='project__name',
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.ProjectGroup.projects.through
        fields = [
            'project_group',
            'project_group_name',
            'project',
            'project_name',
        ]


class ProjectGroupMembershipViewSet(mixins.CreateModelMixin,
                                    mixins.RetrieveModelMixin,
                                    mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    viewsets.GenericViewSet):
    """List of project groups members that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#managing-project-roles
    """

    queryset = models.ProjectGroup.projects.through.objects.all()
    serializer_class = serializers.ProjectGroupMembershipSerializer
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend,)
    filter_class = ProjectGroupMembershipFilter

    def perform_create(self, serializer):
        super(ProjectGroupMembershipViewSet, self).perform_create(serializer)

        project = serializer.validated_data['project']
        project_group = serializer.validated_data['projectgroup']

        event_logger.project_group_membership.info(
            'Project {project_name} has been added to project group {project_group_name}.',
            event_type='project_added_to_project_group',
            event_context={
                'project': project,
                'project_group': project_group,
            })

    def perform_destroy(self, instance):
        super(ProjectGroupMembershipViewSet, self).perform_destroy(instance)

        project = instance.project
        project_group = instance.projectgroup
        event_logger.project_group_membership.info(
            'Project {project_name} has been removed from project group {project_group_name}.',
            event_type='project_removed_from_project_group',
            event_context={
                'project': project,
                'project_group': project_group,
            })

# XXX: This should be put to models
filters.set_permissions_for_model(
    models.ProjectGroup.projects.through,
    customer_path='projectgroup__customer',
)


class UserFilter(django_filters.FilterSet):
    project_group = django_filters.CharFilter(
        name='groups__projectrole__project__project_groups__name',
        distinct=True,
        lookup_type='icontains',
    )
    project = django_filters.CharFilter(
        name='groups__projectrole__project__name',
        distinct=True,
        lookup_type='icontains',
    )

    full_name = django_filters.CharFilter(lookup_type='icontains')
    username = django_filters.CharFilter()
    native_name = django_filters.CharFilter(lookup_type='icontains')
    job_title = django_filters.CharFilter(lookup_type='icontains')
    email = django_filters.CharFilter(lookup_type='icontains')
    is_active = django_filters.BooleanFilter()

    class Meta(object):
        model = User
        fields = [
            'full_name',
            'native_name',
            'organization',
            'organization_approved',
            'email',
            'phone_number',
            'description',
            'job_title',
            'project',
            'project_group',
            'username',
            'civil_number',
            'is_active',
        ]
        order_by = [
            'full_name',
            'native_name',
            'organization',
            'organization_approved',
            'email',
            'phone_number',
            'description',
            'job_title',
            'username',
            'is_active',
            # descending
            '-full_name',
            '-native_name',
            '-organization',
            '-organization_approved',
            '-email',
            '-phone_number',
            '-description',
            '-job_title',
            '-username',
            '-is_active',
        ]


class UserViewSet(viewsets.ModelViewSet):
    """
    List of NodeConductor users.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#user-management
    """

    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    lookup_field = 'uuid'
    permission_classes = (
        rf_permissions.IsAuthenticated,
        permissions.IsAdminOrOwnerOrOrganizationManager,
    )
    filter_class = UserFilter

    def get_queryset(self):
        user = self.request.user
        queryset = super(UserViewSet, self).get_queryset()

        # ?current
        current_user = self.request.query_params.get('current')
        if current_user is not None and not user.is_anonymous():
            queryset = User.objects.filter(uuid=user.uuid)

        # TODO: refactor to a separate endpoint or structure
        # a special query for all users with assigned privileges that the current user can remove privileges from
        if 'potential' in self.request.query_params:
            connected_customers_query = models.Customer.objects.all()
            # is user is not staff, allow only connected customers
            if not user.is_staff:
                # XXX: Let the DB cry...
                connected_customers_query = connected_customers_query.filter(
                    Q(roles__permission_group__user=user)
                    |
                    Q(projects__roles__permission_group__user=user)
                    |
                    Q(project_groups__roles__permission_group__user=user)
                ).distinct()

            # check if we need to filter potential users by a customer
            potential_customer = self.request.query_params.get('potential_customer')
            if potential_customer:
                connected_customers_query = connected_customers_query.filter(uuid=potential_customer)
                connected_customers_query = filters.filter_queryset_for_user(connected_customers_query, user)

            connected_customers = list(connected_customers_query.all())
            potential_organization = self.request.query_params.get('potential_organization')
            if potential_organization is not None:
                potential_organizations = potential_organization.split(',')
            else:
                potential_organizations = []

            queryset = queryset.filter(is_staff=False).filter(
                # customer users
                Q(
                    groups__customerrole__customer__in=connected_customers,
                )
                |
                Q(
                    groups__projectrole__project__customer__in=connected_customers,
                )
                |
                Q(
                    groups__projectgrouprole__project_group__customer__in=connected_customers,
                )
                |
                # users with no role
                Q(
                    groups__customerrole=None,
                    groups__projectrole=None,
                    groups__projectgrouprole=None,
                    organization_approved=True,
                    organization__in=potential_organizations,
                )
            ).distinct()

        organization_claimed = self.request.query_params.get('organization_claimed')
        if organization_claimed is not None:
            queryset = queryset.exclude(organization__isnull=True).exclude(organization__exact='')

        if not user.is_staff:
            queryset = queryset.filter(is_active=True)
            # non-staff users cannot see staff through rest
            queryset = queryset.filter(is_staff=False)

        return queryset

    @detail_route(methods=['post'])
    def password(self, request, uuid=None):
        user = self.get_object()

        serializer = serializers.PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data['password']
        user.set_password(new_password)
        user.save()

        return Response({'detail': "Password has been successfully updated"},
                        status=status.HTTP_200_OK)

    @detail_route(methods=['post'])
    def claim_organization(self, request, uuid=None):
        instance = self.get_object()

        # check if organization name is valid
        serializer = serializers.UserOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if instance.organization:
            return Response({'detail': "User has an existing organization claim."},
                            status=status.HTTP_409_CONFLICT)

        organization = serializer.validated_data['organization']

        instance.organization = organization
        instance.organization_approved = False
        instance.save()

        event_logger.user_organization.info(
            'User {affected_user_username} has claimed organization {affected_organization}.',
            event_type='user_organization_claimed',
            event_context={
                'affected_user': instance,
                'affected_organization': instance.organization,
            })

        return Response({'detail': "User request for joining the organization has been successfully submitted."},
                        status=status.HTTP_200_OK)

    @detail_route(methods=['post'])
    def approve_organization(self, request, uuid=None):
        instance = self.get_object()

        instance.organization_approved = True
        instance.save()

        event_logger.user_organization.info(
            'User {affected_user_username} has been approved for organization {affected_organization}.',
            event_type='user_organization_approved',
            event_context={
                'affected_user': instance,
                'affected_organization': instance.organization,
            })

        return Response({'detail': "User request for joining the organization has been successfully approved"},
                        status=status.HTTP_200_OK)

    @detail_route(methods=['post'])
    def reject_organization(self, request, uuid=None):
        instance = self.get_object()
        old_organization = instance.organization
        instance.organization = ""
        instance.organization_approved = False
        instance.save()

        event_logger.user_organization.info(
            'User {affected_user_username} claim for organization {affected_organization} has been rejected.',
            event_type='user_organization_rejected',
            event_context={
                'affected_user': instance,
                'affected_organization': old_organization,
            })

        return Response({'detail': "User has been successfully rejected from the organization"},
                        status=status.HTTP_200_OK)

    @detail_route(methods=['post'])
    def remove_organization(self, request, uuid=None):
        instance = self.get_object()
        old_organization = instance.organization
        instance.organization_approved = False
        instance.organization = ""
        instance.save()

        event_logger.user_organization.info(
            'User {affected_user_username} has been removed from organization {affected_organization}.',
            event_type='user_organization_removed',
            event_context={
                'affected_user': instance,
                'affected_organization': old_organization,
            })

        return Response({'detail': "User has been successfully removed from the organization"},
                        status=status.HTTP_200_OK)


# TODO: cover filtering/ordering with tests
class ProjectPermissionFilter(django_filters.FilterSet):
    project = django_filters.CharFilter(
        name='group__projectrole__project__uuid',
    )
    project_url = core_filters.URLFilter(
        viewset=ProjectViewSet,
        name='group__projectrole__project__uuid',
    )
    user_url = core_filters.URLFilter(
        viewset=UserViewSet,
        name='user__uuid',
    )
    username = django_filters.CharFilter(
        name='user__username',
        lookup_type='exact',
    )
    full_name = django_filters.CharFilter(
        name='user__full_name',
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        name='user__native_name',
        lookup_type='icontains',
    )
    role = core_filters.MappedChoiceFilter(
        name='group__projectrole__role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
            # TODO: Removing this drops support of filtering by numeric codes
            (models.ProjectRole.ADMINISTRATOR, 'Administrator'),
            (models.ProjectRole.MANAGER, 'Manager'),
        ),
        choice_mappings={
            'admin': models.ProjectRole.ADMINISTRATOR,
            'manager': models.ProjectRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = [
            'role',
            'project',
            'username',
            'full_name',
            'native_name',
        ]
        order_by = [
            'user__username',
            'user__full_name',
            'user__native_name',
            # desc
            '-user__username',
            '-user__full_name',
            '-user__native_name',
        ]


class ProjectPermissionViewSet(mixins.CreateModelMixin,
                               mixins.RetrieveModelMixin,
                               mixins.ListModelMixin,
                               mixins.DestroyModelMixin,
                               viewsets.GenericViewSet):
    # See CustomerPermissionViewSet for implementation details.

    queryset = User.groups.through.objects.exclude(group__projectrole=None)
    serializer_class = serializers.ProjectPermissionSerializer
    permission_classes = (rf_permissions.IsAuthenticated,)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend,)
    filter_class = ProjectPermissionFilter

    def can_manage_roles_for(self, project):
        user = self.request.user
        if user.is_staff:
            return True

        if project.customer.has_user(user, models.CustomerRole.OWNER):
            return True

        for project_group in project.project_groups.iterator():
            if project_group.has_user(user, models.ProjectGroupRole.MANAGER):
                return True

        return False

    def get_queryset(self):
        queryset = super(ProjectPermissionViewSet, self).get_queryset()

        # TODO: refactor against django filtering
        user_uuid = self.request.query_params.get('user', None)
        if user_uuid is not None:
            queryset = queryset.filter(user__uuid=user_uuid)

        return queryset

    def perform_create(self, serializer):
        affected_project = serializer.validated_data['project']

        if not self.can_manage_roles_for(affected_project):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_project.customer.validate_quota_change({'nc_user_count': 1}, raise_exception=True)

        super(ProjectPermissionViewSet, self).perform_create(serializer)

    def perform_destroy(self, instance):
        affected_user = instance.user
        affected_project = instance.group.projectrole.project
        role = instance.group.projectrole.role_type

        if not self.can_manage_roles_for(affected_project):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_project.remove_user(affected_user, role)


class ProjectGroupPermissionFilter(django_filters.FilterSet):
    project_group = django_filters.CharFilter(
        name='group__projectgrouprole__project_group__uuid',
    )
    project_group_url = core_filters.URLFilter(
        viewset=ProjectGroupViewSet,
        name='group__projectgrouprole__project_group__uuid',
    )
    user_url = core_filters.URLFilter(
        viewset=UserViewSet,
        name='user__uuid',
    )
    username = django_filters.CharFilter(
        name='user__username',
        lookup_type='exact',
    )
    full_name = django_filters.CharFilter(
        name='user__full_name',
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        name='user__native_name',
        lookup_type='icontains',
    )
    role = core_filters.MappedChoiceFilter(
        name='group__projectgrouprole__role_type',
        choices=(
            ('manager', 'Manager'),
            # TODO: Removing this drops support of filtering by numeric codes
            (models.ProjectGroupRole.MANAGER, 'Manager'),
        ),
        choice_mappings={
            'manager': models.ProjectGroupRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = [
            'role',
            'project_group',
            'username',
            'full_name',
            'native_name',
        ]
        order_by = [
            'user__username',
            'user__full_name',
            'user__native_name',
            # desc
            '-user__username',
            '-user__full_name',
            '-user__native_name',

        ]


class ProjectGroupPermissionViewSet(mixins.CreateModelMixin,
                                    mixins.RetrieveModelMixin,
                                    mixins.ListModelMixin,
                                    mixins.DestroyModelMixin,
                                    viewsets.GenericViewSet):
    # See CustomerPermissionViewSet for implementation details.
    queryset = User.groups.through.objects.exclude(group__projectgrouprole=None)
    serializer_class = serializers.ProjectGroupPermissionSerializer
    permission_classes = (rf_permissions.IsAuthenticated,)
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filter_class = ProjectGroupPermissionFilter

    def can_manage_roles_for(self, project_group):
        user = self.request.user
        if user.is_staff:
            return True

        if project_group.customer.has_user(user, models.CustomerRole.OWNER):
            return True

        return False

    def get_queryset(self):
        queryset = super(ProjectGroupPermissionViewSet, self).get_queryset()

        # TODO: refactor against django filtering
        user_uuid = self.request.query_params.get('user', None)
        if user_uuid is not None:
            queryset = queryset.filter(user__uuid=user_uuid)

        # XXX: This should be removed after permissions refactoring
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(group__projectgrouprole__project_group__customer__roles__permission_group__user=self.request.user,
                  group__projectgrouprole__project_group__customer__roles__role_type=models.CustomerRole.OWNER)
                |
                Q(group__projectgrouprole__project_group__projects__roles__permission_group__user=self.request.user)
                |
                Q(group__projectgrouprole__project_group__roles__permission_group__user=self.request.user)
            ).distinct()

        return queryset

    def perform_create(self, serializer):
        affected_project_group = serializer.validated_data['project_group']

        if not self.can_manage_roles_for(affected_project_group):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_project_group.customer.validate_quota_change({'nc_user_count': 1}, raise_exception=True)

        super(ProjectGroupPermissionViewSet, self).perform_create(serializer)

    def perform_destroy(self, instance):
        affected_user = instance.user
        affected_project_group = instance.group.projectgrouprole.project_group
        role = instance.group.projectgrouprole.role_type

        if not self.can_manage_roles_for(affected_project_group):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_project_group.remove_user(affected_user, role)


class CustomerPermissionFilter(django_filters.FilterSet):
    customer = django_filters.CharFilter(
        name='group__customerrole__customer__uuid',
    )
    customer_url = core_filters.URLFilter(
        viewset=CustomerViewSet,
        name='group__customerrole__customer__uuid',
    )
    user_url = core_filters.URLFilter(
        viewset=UserViewSet,
        name='user__uuid',
    )
    username = django_filters.CharFilter(
        name='user__username',
        lookup_type='exact',
    )
    full_name = django_filters.CharFilter(
        name='user__full_name',
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        name='user__native_name',
        lookup_type='icontains',
    )
    role = core_filters.MappedChoiceFilter(
        name='group__customerrole__role_type',
        choices=(
            ('owner', 'Owner'),
            # TODO: Removing this drops support of filtering by numeric codes
            (models.CustomerRole.OWNER, 'Owner'),
        ),
        choice_mappings={
            'owner': models.CustomerRole.OWNER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = [
            'role',
            'customer',
            'username',
            'full_name',
            'native_name',
        ]
        order_by = [
            'user__username',
            'user__full_name',
            'user__native_name',
            # desc
            '-user__username',
            '-user__full_name',
            '-user__native_name',

        ]


class CustomerPermissionViewSet(mixins.CreateModelMixin,
                                mixins.RetrieveModelMixin,
                                mixins.ListModelMixin,
                                mixins.DestroyModelMixin,
                                viewsets.GenericViewSet):
    queryset = User.groups.through.objects.exclude(group__customerrole=None)
    serializer_class = serializers.CustomerPermissionSerializer
    permission_classes = (
        rf_permissions.IsAuthenticated,
        # DjangoObjectPermissions not used on purpose, see below.
        # rf_permissions.DjangoObjectPermissions,
    )
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filter_class = CustomerPermissionFilter

    def can_manage_roles_for(self, customer):
        user = self.request.user
        if user.is_staff:
            return True

        if customer.has_user(user, models.CustomerRole.OWNER):
            return True

        return False

    def get_queryset(self):
        queryset = super(CustomerPermissionViewSet, self).get_queryset()

        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(group__customerrole__customer__roles__permission_group__user=self.request.user,
                  group__customerrole__customer__roles__role_type=models.CustomerRole.OWNER)
                |
                Q(group__customerrole__customer__projects__roles__permission_group__user=self.request.user)
                |
                Q(group__customerrole__customer__project_groups__roles__permission_group__user=self.request.user)
            ).distinct()

        return queryset

    # DjangoObjectPermissions is not used because it cannot enforce
    # create permissions based on the body of the request.
    # Another reason is to foster symmetry: check for both granting
    # and revocation are kept in one place - the view.
    def perform_create(self, serializer):
        affected_customer = serializer.validated_data['customer']

        if not self.can_manage_roles_for(affected_customer):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_customer.validate_quota_change({'nc_user_count': 1}, raise_exception=True)

        # It would be nice to put customer.add_user() logic here as well.
        # But it is pushed down to serializer.create() because otherwise
        # no url will be rendered in response.
        super(CustomerPermissionViewSet, self).perform_create(serializer)

    def perform_destroy(self, instance):
        affected_user = instance.user
        affected_customer = instance.group.customerrole.customer
        role = instance.group.customerrole.role_type

        if not self.can_manage_roles_for(affected_customer):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_customer.remove_user(affected_user, role)


class CreationTimeStatsView(views.APIView):

    def get(self, request, format=None):
        month = 60 * 60 * 24 * 30
        data = {
            'start_timestamp': request.query_params.get('from', int(time.time() - month)),
            'end_timestamp': request.query_params.get('to', int(time.time())),
            'segments_count': request.query_params.get('datapoints', 6),
            'model_name': request.query_params.get('type', 'customer'),
        }

        serializer = serializers.CreationTimeStatsSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        stats = serializer.get_stats(request.user)
        return Response(stats, status=status.HTTP_200_OK)


class SshKeyFilter(django_filters.FilterSet):
    uuid = django_filters.CharFilter()
    user_uuid = django_filters.CharFilter(
        name='user__uuid'
    )
    name = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = core_models.SshPublicKey
        fields = [
            'name',
            'fingerprint',
            'uuid',
            'user_uuid'
        ]
        order_by = [
            'name',
            '-name',
        ]


class SshKeyViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.DestroyModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """
    List of SSH public keys that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#key-management
    """

    queryset = core_models.SshPublicKey.objects.all()
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'
    filter_backends = (rf_filters.DjangoFilterBackend, core_filters.StaffOrUserFilter)
    filter_class = SshKeyFilter

    def perform_create(self, serializer):
        user = self.request.user
        name = serializer.validated_data['name']

        if core_models.SshPublicKey.objects.filter(user=user, name=name).exists():
            raise rf_serializers.ValidationError({'name': ['This field must be unique.']})

        serializer.save(user=user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except Exception as e:
            logger.exception("Can't remove SSH public key from backend")
            raise APIException(e)


class ServiceSettingsFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_type='icontains')
    type = core_filters.MappedChoiceFilter(
        choices=SupportedServices.Types.get_direct_filter_mapping(),
        choice_mappings=SupportedServices.Types.get_reverse_filter_mapping(),
    )
    state = core_filters.MappedChoiceFilter(
        choices=(
            ('sync_scheduled', 'Sync Scheduled'),
            ('syncing', 'Syncing'),
            ('in_sync', 'In Sync'),
            ('erred', 'Erred'),
        ),
        choice_mappings={
            'sync_scheduled': core_models.SynchronizationStates.SYNCING_SCHEDULED,
            'syncing': core_models.SynchronizationStates.SYNCING,
            'in_sync': core_models.SynchronizationStates.IN_SYNC,
            'erred': core_models.SynchronizationStates.ERRED,
        },
    )

    class Meta(object):
        model = models.ServiceSettings
        fields = ('name', 'type', 'state')


class ServiceSettingsViewSet(mixins.RetrieveModelMixin,
                             mixins.UpdateModelMixin,
                             mixins.ListModelMixin,
                             viewsets.GenericViewSet):
    queryset = models.ServiceSettings.objects.filter()
    serializer_class = serializers.ServiceSettingsSerializer
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    filter_class = ServiceSettingsFilter
    lookup_field = 'uuid'

    def perform_create(self, serializer):
        instance = serializer.save()
        send_task('structure', 'sync_service_settings')(instance.uuid.hex, initial=True)


class ServiceViewSet(viewsets.GenericViewSet):
    """ The list of supported services and resources. """

    def list(self, request):
        return Response(SupportedServices.get_services_with_resources(request))


class ResourceViewSet(viewsets.GenericViewSet):
    """ The summary list of all user resources. """

    def list(self, request):

        def fetch_data(view_name, params):
            response = request_api(request, view_name, params=params)
            if not response.success:
                raise APIException(response.data)
            return response

        def clear_query(keys):
            params = {}
            for key in keys:
                if key in request.query_params:
                    params[key] = request.query_params.get(key)
            return params

        data = []
        types = request.query_params.getlist('resource_type', [])

        for resource_type, resources_url in SupportedServices.get_resources(request).items():
            if types != [] and resource_type not in types:
                continue

            params = clear_query(('name', 'project_uuid'))
            response = fetch_data(resources_url, params)

            if response.total and response.total > len(response.data):
                params['page_size'] = response.total
                response = fetch_data(resources_url, params)
            data += response.data

        page = self.paginate_queryset(data)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(data)


class UpdateOnlyByPaidCustomerMixin(object):
    """ Allow modification of entities if their customer's balance is positive. """

    @staticmethod
    def _check_paid_status(settings, customer):
        # Check for shared settings only or missed settings in case of IaaS
        if settings is None or settings.shared:
            if customer and customer.balance is not None and customer.balance <= 0:
                raise PermissionDenied(
                    "Your balance is %s. Action disabled." % customer.balance)

    def initial(self, request, *args, **kwargs):
        if hasattr(self, 'PaidControl') and self.action and self.action not in ('list', 'retrieve', 'create'):
            if django_settings.NODECONDUCTOR.get('SUSPEND_UNPAID_CUSTOMERS'):
                entity = self.get_object()

                def get_obj(name):
                    try:
                        args = getattr(self.PaidControl, '%s_path' % name).split('__')
                    except AttributeError:
                        return None
                    return reduce(getattr, args, entity)

                self._check_paid_status(get_obj('settings'), get_obj('customer'))

        return super(UpdateOnlyByPaidCustomerMixin, self).initial(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if django_settings.NODECONDUCTOR.get('SUSPEND_UNPAID_CUSTOMERS'):
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            def get_obj(name):
                try:
                    args = getattr(self.PaidControl, '%s_path' % name).split('__')
                except AttributeError:
                    return None
                obj = serializer.validated_data[args[0]]
                if len(args) > 1:
                    obj = reduce(getattr, args[1:], obj)
                return obj

            self._check_paid_status(get_obj('settings'), get_obj('customer'))

        return super(UpdateOnlyByPaidCustomerMixin, self).create(request, *args, **kwargs)


class BaseServiceFilter(django_filters.FilterSet):
    customer_uuid = django_filters.CharFilter(name='customer__uuid')
    customer = core_filters.URLFilter(viewset=CustomerViewSet, name='customer__uuid')

    class Meta(object):
        model = models.Service


class BaseServiceViewSet(UpdateOnlyByPaidCustomerMixin,
                         core_mixins.UserContextMixin,
                         viewsets.ModelViewSet):

    class PaidControl:
        customer_path = 'customer'
        settings_path = 'settings'

    queryset = NotImplemented
    serializer_class = NotImplemented
    import_serializer_class = NotImplemented
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    filter_class = BaseServiceFilter
    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.action == 'link':
            return self.import_serializer_class
        return super(BaseServiceViewSet, self).get_serializer_class()

    def get_serializer_context(self):
        context = super(BaseServiceViewSet, self).get_serializer_context()
        if self.action == 'link':
            context['service'] = self.get_object()
        return context

    @detail_route(methods=['get', 'post'])
    def link(self, request, uuid=None):
        if self.request.method == 'GET':
            service = self.get_object()
            try:
                # project_uuid can be supplied in order to get a list of resources
                # available for import (link) based on project, depends on backend implementation
                project_uuid = request.query_params.get('project_uuid')
                if project_uuid:
                    spl_class = SupportedServices.get_related_models(service)['service_project_link']
                    try:
                        spl = spl_class.objects.get(project__uuid=project_uuid, service=service)
                    except:
                        pass
                    else:
                        backend = spl.get_backend()
                else:
                    backend = service.get_backend()

                try:
                    resources = backend.get_resources_for_import()
                except ServiceBackendNotImplemented:
                    resources = []

                return Response(resources)
            except ServiceBackendError as e:
                raise APIException(e)
        else:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            customer = serializer.validated_data.pop('project').customer
            if not request.user.is_staff and not customer.has_user(request.user):
                raise PermissionDenied(
                    "Only customer owner or staff are allowed to perform this action.")

            try:
                serializer.save()
            except ServiceBackendError as e:
                raise APIException(e)

            return Response(serializer.data, status=status.HTTP_200_OK)


class BaseServiceProjectLinkFilter(django_filters.FilterSet):
    service_uuid = django_filters.CharFilter(name='service__uuid')
    project_uuid = django_filters.CharFilter(name='project__uuid')
    project = core_filters.URLFilter(viewset=ProjectViewSet, name='project__uuid')

    class Meta(object):
        model = models.ServiceProjectLink


class BaseServiceProjectLinkViewSet(UpdateOnlyByPaidCustomerMixin,
                                    mixins.CreateModelMixin,
                                    mixins.RetrieveModelMixin,
                                    mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    viewsets.GenericViewSet):

    class PaidControl:
        customer_path = 'service__customer'
        settings_path = 'service__settings'

    queryset = NotImplemented
    serializer_class = NotImplemented
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    filter_class = BaseServiceProjectLinkFilter

    def perform_create(self, serializer):
        instance = serializer.save()
        send_task('structure', 'sync_service_project_links')(instance.to_string(), initial=True)


class BaseResourceProjectFilter(object):
    def filter_queryset(self, request, queryset, view):
        project_uuid = request.query_params.get('project_uuid')
        if project_uuid:
            return queryset.filter(service_project_link__project__uuid=project_uuid)
        return queryset


class BaseResourceViewSet(UpdateOnlyByPaidCustomerMixin,
                          core_mixins.UserContextMixin,
                          viewsets.ModelViewSet):

    class PaidControl:
        customer_path = 'service_project_link__service__customer'
        settings_path = 'service_project_link__service__settings'

    queryset = NotImplemented
    serializer_class = NotImplemented
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (
        filters.GenericRoleFilter,
        rf_filters.DjangoFilterBackend,
        BaseResourceProjectFilter
    )

    def safe_operation(valid_state=None):
        def decorator(view_fn):
            @functools.wraps(view_fn)
            def wrapped(self, request, *args, **kwargs):
                message = "Performing %s operation is not allowed for resource in its current state"
                operation_name = view_fn.__name__

                try:
                    with transaction.atomic():
                        resource = self.get_object()
                        is_admin = resource.service_project_link.project.has_user(
                            request.user, models.ProjectRole.ADMINISTRATOR)

                        if not is_admin and not request.user.is_staff:
                            raise PermissionDenied(
                                "Only project administrator or staff allowed to perform this action.")

                        if valid_state and resource.state != valid_state:
                            raise core_exceptions.IncorrectStateException(message % operation_name)

                        # Important! We are passing back the instance from current transaction to a view
                        try:
                            view_fn(self, request, resource, *args, **kwargs)
                        except ServiceBackendNotImplemented:
                            raise MethodNotAllowed(operation_name)

                except TransitionNotAllowed:
                    raise core_exceptions.IncorrectStateException(message % operation_name)

                except IntegrityError:
                    return Response({'status': '%s was not scheduled' % operation_name},
                                    status=status.HTTP_400_BAD_REQUEST)

                return Response({'status': '%s was scheduled' % operation_name},
                                status=status.HTTP_202_ACCEPTED)

            return wrapped
        return decorator

    def initial(self, request, *args, **kwargs):
        if self.action in ('update', 'partial_update'):
            resource = self.get_object()
            if resource.state not in resource.States.STABLE_STATES:
                raise core_exceptions.IncorrectStateException(
                    'Modification allowed in stable states only')

        elif self.action in ('stop', 'start', 'resize'):
            resource = self.get_object()
            if resource.state == resource.States.PROVISIONING_SCHEDULED:
                raise core_exceptions.IncorrectStateException(
                    'Provisioning scheduled. Disabled modifications.')

        super(BaseResourceViewSet, self).initial(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super(BaseResourceViewSet, self).get_queryset()

        order = self.request.query_params.get('o', None)
        if order == 'start_time':
            queryset = queryset.extra(select={
                'is_null': 'CASE WHEN start_time IS NULL THEN 0 ELSE 1 END'}) \
                .order_by('is_null', 'start_time')
        elif order == '-start_time':
            queryset = queryset.extra(select={
                'is_null': 'CASE WHEN start_time IS NULL THEN 0 ELSE 1 END'}) \
                .order_by('-is_null', '-start_time')

        return queryset

    def perform_create(self, serializer):
        if serializer.validated_data['service_project_link'].state == core_models.SynchronizationStates.ERRED:
            raise core_exceptions.IncorrectStateException(
                detail='Cannot modify resource if its service project link in erred state.')

        try:
            self.perform_provision(serializer)
        except ServiceBackendError as e:
            raise APIException(e)

    def perform_update(self, serializer):
        spl = self.get_object().service_project_link
        if spl.state == core_models.SynchronizationStates.ERRED:
            raise core_exceptions.IncorrectStateException(
                detail='Cannot modify resource if its service project link in erred state.')

        serializer.save()

    def perform_provision(self, serializer):
        raise NotImplementedError

    @safe_operation(valid_state=models.Resource.States.OFFLINE)
    def destroy(self, request, resource, uuid=None):
        if resource.backend_id:
            backend = resource.get_backend()
            backend.destroy(resource)
        else:
            self.perform_destroy(resource)

    @detail_route(methods=['post'])
    @safe_operation()
    def unlink(self, request, resource, uuid=None):
        self.perform_destroy(resource)

    @detail_route(methods=['post'])
    @safe_operation(valid_state=models.Resource.States.OFFLINE)
    def start(self, request, resource, uuid=None):
        backend = resource.get_backend()
        backend.start(resource)

    @detail_route(methods=['post'])
    @safe_operation(valid_state=models.Resource.States.ONLINE)
    def stop(self, request, resource, uuid=None):
        backend = resource.get_backend()
        backend.stop(resource)

    @detail_route(methods=['post'])
    @safe_operation(valid_state=models.Resource.States.ONLINE)
    def restart(self, request, resource, uuid=None):
        backend = resource.get_backend()
        backend.restart(resource)
