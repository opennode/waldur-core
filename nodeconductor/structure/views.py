from __future__ import unicode_literals

import time
import logging
import functools
from collections import defaultdict

from datetime import timedelta

from django.conf import settings as django_settings
from django.contrib import auth
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import six, timezone
from django_fsm import TransitionNotAllowed

from rest_framework import filters as rf_filters
from rest_framework import mixins
from rest_framework import permissions as rf_permissions
from rest_framework import serializers as rf_serializers
from rest_framework import status
from rest_framework import views
from rest_framework import viewsets
from rest_framework import generics
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed, NotFound, APIException
from rest_framework.response import Response
import reversion

from nodeconductor.core import filters as core_filters
from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import exceptions as core_exceptions
from nodeconductor.core import serializers as core_serializers
from nodeconductor.core.views import BaseSummaryView, StateExecutorViewSet
from nodeconductor.core.utils import request_api, datetime_to_timestamp, sort_dict
from nodeconductor.monitoring.filters import SlaFilter, MonitoringItemFilter
from nodeconductor.quotas.models import QuotaModelMixin, Quota
from nodeconductor.structure import SupportedServices, ServiceBackendError, ServiceBackendNotImplemented
from nodeconductor.structure import filters
from nodeconductor.structure import permissions
from nodeconductor.structure import models
from nodeconductor.structure import serializers
from nodeconductor.structure import managers
from nodeconductor.structure.log import event_logger
from nodeconductor.structure.signals import resource_imported
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.structure.metadata import check_operation, ResourceActionsMetadata

logger = logging.getLogger(__name__)

User = auth.get_user_model()


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = models.Customer.objects.all()
    serializer_class = serializers.CustomerSerializer
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend,)
    filter_class = filters.CustomerFilter

    def list(self, request, *args, **kwargs):
        """
        To get a list of customers, run GET against */api/customers/* as authenticated user. Note that a user can
        only see connected customers:

        - customers that the user owns
        - customers that have a project where user has a role
        """
        return super(CustomerViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Optional `field` query parameter (can be list) allows to limit what fields are returned.
        For example, given request /api/customers/<uuid>/?field=uuid&field=name you get response like this:

        .. code-block:: javascript

            {
                "uuid": "90bcfe38b0124c9bbdadd617b5d739f5",
                "name": "Ministry of Bells"
            }
        """
        return super(CustomerViewSet, self).retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        A new customer can only be created by users with staff privilege (is_staff=True).
        Example of a valid request:

        .. code-block:: http

            POST /api/customers/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "Customer A",
                "native_name": "Customer A",
                "abbreviation": "CA",
                "contact_details": "Luhamaa 28, 10128 Tallinn",
            }
        """
        return super(CustomerViewSet, self).create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Deletion of a customer is done through sending a **DELETE** request to the customer instance URI. Please note,
        that if a customer has connected projects or project groups, deletion request will fail with 409 response code.

        Valid request example (token is user specific):

        .. code-block:: http

            DELETE /api/customers/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com
        """
        return super(CustomerViewSet, self).destroy(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'users':
            return serializers.CustomerUserSerializer
        return super(CustomerViewSet, self).get_serializer_class()

    def get_serializer_context(self):
        context = super(CustomerViewSet, self).get_serializer_context()
        if self.action == 'users':
            context['customer'] = self.get_object()
        return context

    def get_queryset(self):
        queryset = super(CustomerViewSet, self).get_queryset()
        if self.action in ('list', 'retrieve'):
            queryset = self.get_serializer_class().eager_load(queryset)
        return queryset

    def perform_create(self, serializer):
        customer = serializer.save()
        if not self.request.user.is_staff:
            customer.add_user(self.request.user, models.CustomerRole.OWNER)

    @detail_route()
    def balance_history(self, request, uuid=None):
        default_start = timezone.now() - timedelta(days=30)  # one month ago
        timestamp_interval_serializer = core_serializers.TimestampIntervalSerializer(data={
            'start': request.query_params.get('from', datetime_to_timestamp(default_start)),
            'end': request.query_params.get('to', datetime_to_timestamp(timezone.now()))
        })
        timestamp_interval_serializer.is_valid(raise_exception=True)
        filter_data = timestamp_interval_serializer.get_filter_data()

        customer = self.get_object()
        queryset = models.BalanceHistory.objects.filter(customer=customer).order_by('created')
        queryset = queryset.filter(created__gte=filter_data['start'], created__lte=filter_data['end'])

        serializer = serializers.BalanceHistorySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @detail_route()
    def users(self, request, uuid=None):
        """ A list of users connected to the customer """
        customer = self.get_object()
        queryset = self.paginate_queryset(customer.get_users())
        serializer = self.get_serializer(queryset, many=True)
        return self.get_paginated_response(serializer.data)


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


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = models.Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, core_filters.DjangoMappingFilterBackend)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)
    filter_class = filters.ProjectFilter

    def list(self, request, *args, **kwargs):
        """
        To get a list of projects, run **GET** against */api/projects/* as authenticated user.
        Here you can also check actual value for project quotas and project usage

        Note that a user can only see connected projects:

        - projects that the user owns as a customer
        - projects where user has any role

        Supported logic filters:

        - ?can_manage - return a list of projects where current user is manager, group manager or a customer owner;
        - ?can_admin - return a list of projects where current user is admin;
        """
        return super(ProjectViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Optional `field` query parameter (can be list) allows to limit what fields are returned.
        For example, given request /api/projects/<uuid>/?field=uuid&field=name you get response like this:

        .. code-block:: javascript

            {
                "uuid": "90bcfe38b0124c9bbdadd617b5d739f5",
                "name": "Default"
            }
        """
        return super(ProjectViewSet, self).retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        A new project can be created by users with staff privilege (is_staff=True) or customer owners.
        Project resource quota is optional. Example of a valid request:

        .. code-block:: http

            POST /api/projects/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "Project A",
                "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
                "project_groups": [
                    { "url": "http://localhost:8000/api/project-groups/b04f53e72e9b46949fa7c3a0ef52cd91/"}
                ]
            }
        """
        return super(ProjectViewSet, self).create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Deletion of a project is done through sending a **DELETE** request to the project instance URI.
        Please note, that if a project has connected instances, deletion request will fail with 409 response code.

        Valid request example (token is user specific):

        .. code-block:: http

            DELETE /api/projects/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com
        """
        return super(ProjectViewSet, self).destroy(request, *args, **kwargs)

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

        if self.action in ('list', 'retrieve'):
            queryset = self.get_serializer_class().eager_load(queryset)
        return queryset

    def perform_create(self, serializer):
        customer = serializer.validated_data['customer']
        project_groups = serializer.validated_data['project_groups']

        if not self.can_create_project_with(customer, project_groups):
            raise PermissionDenied('You do not have permission to perform this action.')

        customer.validate_quota_change({'nc_project_count': 1}, raise_exception=True)

        super(ProjectViewSet, self).perform_create(serializer)


class ProjectGroupViewSet(viewsets.ModelViewSet):
    queryset = models.ProjectGroup.objects.all()
    serializer_class = serializers.ProjectGroupSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, core_filters.DjangoMappingFilterBackend)
    # permission_classes = (permissions.IsAuthenticated,)  # TODO: Add permissions for Create/Update
    filter_class = filters.ProjectGroupFilter

    def list(self, request, *args, **kwargs):
        """
        To get a list of projects groups, run **GET** against */api/project-groups/* as authenticated user.
        Note that a user can only see connected project groups:

        - project groups that the user owns as a customer;
        - project groups with projects where user has a role.

        A new project group can be created by users with staff privilege (is_staff=True) or customer owners.
        Project group resource quota is optional. Example of a valid request:

        .. code-block:: http

            POST /api/project-groups/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "Project group A",
                "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
            }
        """
        return super(ProjectGroupViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Deletion of a project group is done through sending a **DELETE** request to the project group instance URI.
        Please note, that if a project group has connected projects, deletion request will fail with 409 response code.

        Valid request example (token is user specific):

        .. code-block:: http

            DELETE /api/project-groups/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com
        """
        return super(ProjectGroupViewSet, self).retrieve(request, *args, **kwargs)


class ProjectGroupMembershipViewSet(mixins.CreateModelMixin,
                                    mixins.RetrieveModelMixin,
                                    mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    viewsets.GenericViewSet):
    queryset = models.ProjectGroup.projects.through.objects.all()
    serializer_class = serializers.ProjectGroupMembershipSerializer
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend,)
    filter_class = filters.ProjectGroupMembershipFilter

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

    def list(self, request, *args, **kwargs):
        """
        To get a list of connections between project and a project group,
        run **GET** against */api/project-group-memberships/* as authenticated user.
        Note that a user can only see connections of a project or a project group where a user has a role.

        In order to link project to a project group, **POST** a connection between them to
        */api/project-group-memberships/*.
        Note that project and a project group must be from the same customer.
        For example,

        .. code-block:: http

            POST /api/project-group-memberships/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "project_group": "http://example.com/api/project-groups/736038dc5cac47309111916eb6fe802d/",
                "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
            }
        """
        return super(ProjectGroupMembershipViewSet, self).list(request, *args, **kwargs)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    lookup_field = 'uuid'
    permission_classes = (
        rf_permissions.IsAuthenticated,
        permissions.IsAdminOrOwnerOrOrganizationManager,
    )
    filter_class = filters.UserFilter

    def get_queryset(self):
        user = self.request.user
        queryset = super(UserViewSet, self).get_queryset()

        # ?current
        current_user = self.request.query_params.get('current')
        if current_user is not None and not user.is_anonymous():
            queryset = User.objects.filter(uuid=user.uuid)

        # TODO: refactor to a separate endpoint or structure
        # a special query for all users with assigned privileges that the current user can remove privileges from
        if (not django_settings.NODECONDUCTOR.get('SHOW_ALL_USERS', True) and not user.is_staff) or \
                'potential' in self.request.query_params:
            connected_customers_query = models.Customer.objects.all()
            # is user is not staff, allow only connected customers
            if not user.is_staff:
                # XXX: Let the DB cry...
                connected_customers_query = connected_customers_query.filter(
                    Q(roles__permission_group__user=user) |
                    Q(projects__roles__permission_group__user=user) |
                    Q(project_groups__roles__permission_group__user=user)
                ).distinct()

            # check if we need to filter potential users by a customer
            potential_customer = self.request.query_params.get('potential_customer')
            if potential_customer:
                connected_customers_query = connected_customers_query.filter(uuid=potential_customer)
                connected_customers_query = filter_queryset_for_user(connected_customers_query, user)

            connected_customers = list(connected_customers_query.all())
            potential_organization = self.request.query_params.get('potential_organization')
            if potential_organization is not None:
                potential_organizations = potential_organization.split(',')
            else:
                potential_organizations = []

            queryset = queryset.filter(is_staff=False).filter(
                # customer users
                Q(groups__customerrole__customer__in=connected_customers) |
                Q(groups__projectrole__project__customer__in=connected_customers) |
                Q(groups__projectgrouprole__project_group__customer__in=connected_customers) |
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

    def list(self, request, *args, **kwargs):
        """
        User list is available to all authenticated users. To get a list,
        issue authenticated **GET** request against */api/users/*.

        User list supports several filters. All filters are set in HTTP query section.
        Field filters are listed below. All of the filters apart from ?organization are
        using case insensitive partial matching.

        Several custom filters are supported:

        - ?current - filters out user making a request. Useful for getting information about a currently logged in user.
        - ?civil_number=XXX - filters out users with a specified civil number
        - ?is_active=True|False - show only active (non-active) users
        - ?potential - shows users that have common connections to the customers and are potential collaborators.
          Exclude staff users. Staff users can see all the customers.
        - ?potential_customer=<Customer UUID> - optionally filter potential users by customer UUID
        - ?potential_organization=<organization name> - optionally filter potential unconnected users by
          their organization name
          (deprecated, use `organization plugin <http://nodeconductor-organization.readthedocs.org/en/stable/>`_ instead)
        - ?organization_claimed - show only users with a non-empty organization
          (deprecated, use `organization plugin <http://nodeconductor-organization.readthedocs.org/en/stable/>`_ instead)

        The user can be created either through automated process on login with SAML token, or through a REST call by a user
        with staff privilege.

        Example of a creation request is below.

        .. code-block:: http

            POST /api/users/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "username": "sample-user",
                "full_name": "full name",
                "native_name": "taisnimi",
                "job_title": "senior cleaning manager",
                "email": "example@example.com",
                "civil_number": "12121212",
                "phone_number": "",
                "description": "",
                "organization": "",
            }

        NB! Username field is case-insensitive. So "John" and "john" will be treated as the same user.
        """
        return super(UserViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        User fields can be updated by account owner or user with staff privilege (is_staff=True).
        Following user fields can be updated:

        - organization (deprecated, use
          `organization plugin <http://nodeconductor-organization.readthedocs.org/en/stable/>`_ instead)
        - full_name
        - native_name
        - job_title
        - phone_number
        - email

        Can be done by **PUT**ing a new data to the user URI, i.e. */api/users/<UUID>/* by staff user or account owner.
        Valid request example (token is user specific):

        .. code-block:: http

            PUT /api/users/e0c058d06864441fb4f1c40dee5dd4fd/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "email": "example@example.com",
                "organization": "Bells organization",
            }
        """
        return super(UserViewSet, self).retrieve(request, *args, **kwargs)

    @detail_route(methods=['post'])
    def password(self, request, uuid=None):
        """
        To change a user password, submit a **POST** request to the user's RPC URL, specifying new password
        by staff user or account owner.

        Password is expected to be at least 7 symbols long and contain at least one number
        and at least one lower or upper case.

        Example of a valid request:

        .. code-block:: http

            POST /api/users/e0c058d06864441fb4f1c40dee5dd4fd/password/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "password": "nQvqHzeP123",
            }
        """
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
        """
        **Deprecated, use**
        `organization plugin <http://nodeconductor-organization.readthedocs.org/en/stable/>`_ **instead.**
        """
        instance = self.get_object()

        # check if organization name is valid
        serializer = serializers.UserOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if instance.organization and instance.organization_approved:
            return Response({'detail': "User has approved organization. Remove it before claiming a new one."},
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
        """
        **Deprecated, use**
        `organization plugin <http://nodeconductor-organization.readthedocs.org/en/stable/>`_ **instead.**
        """
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
        """
        **Deprecated, use**
        `organization plugin <http://nodeconductor-organization.readthedocs.org/en/stable/>`_ **instead.**
        """
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
        """
        **Deprecated, use**
        `organization plugin <http://nodeconductor-organization.readthedocs.org/en/stable/>`_ **instead.**
        """
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


class ProjectPermissionViewSet(mixins.CreateModelMixin,
                               mixins.RetrieveModelMixin,
                               mixins.ListModelMixin,
                               mixins.DestroyModelMixin,
                               viewsets.GenericViewSet):
    """
    - Projects are connected to customers, whereas the project may belong to one customer only,
      and the customer may have
      multiple projects.
    - Projects are connected to project groups, whereas the project may belong to multiple project groups,
      and the project group may contain multiple projects.
    - Projects are connected to clouds, whereas the project may contain multiple clouds,
      and the cloud may belong to multiple projects.
    - Staff members can list all available projects of any customer and create new projects.
    - Customer owners can list all projects that belong to any of the customers they own.
      Customer owners can also create projects for the customers they own.
    - Project administrators can list all the projects they are administrators in.
    - Project managers can list all the projects they are managers in.
    """
    # See CustomerPermissionViewSet for implementation details.

    queryset = User.groups.through.objects.exclude(group__projectrole=None)
    serializer_class = serializers.ProjectPermissionSerializer
    permission_classes = (rf_permissions.IsAuthenticated,)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend,)
    filter_class = filters.ProjectPermissionFilter

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

    def list(self, request, *args, **kwargs):
        """
        Project permissions expresses connection of users to a project. Each project has two associated user groups that
        represent project managers and administrators. The link is maintained
        through */api/project-permissions/* endpoint.

        Note that project membership can be viewed and modified only by customer owners, corresponding project group
        managers and staff users.

        To list all visible links, run a **GET** query against a list.
        Response will contain a list of project users and their brief data.

        To add a new user to the project, **POST** a new relationship to */api/project-permissions/* endpoint specifying
        project, user and the role of the user ('admin' or 'manager'):

        .. code-block:: http

            POST /api/project-permissions/ HTTP/1.1
            Accept: application/json
            Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
            Host: example.com

            {
                "project": "http://example.com/api/projects/6c9b01c251c24174a6691a1f894fae31/",
                "role": "manager",
                "user": "http://example.com/api/users/82cec6c8e0484e0ab1429412fe4194b7/"
            }
        """
        return super(ProjectPermissionViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        To remove a user from a project group, delete corresponding connection (**url** field). Successful deletion
        will return status code 204.

        .. code-block:: http

            DELETE /api/project-permissions/42/ HTTP/1.1
            Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
            Host: example.com
        """
        return super(ProjectPermissionViewSet, self).retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        affected_project = serializer.validated_data['project']
        affected_user = serializer.validated_data['user']

        if not self.can_manage_roles_for(affected_project):
            raise PermissionDenied('You do not have permission to perform this action.')

        if not affected_project.customer.get_users().filter(pk=affected_user.pk).exists():
            affected_project.customer.validate_quota_change({'nc_user_count': 1}, raise_exception=True)

        super(ProjectPermissionViewSet, self).perform_create(serializer)

    def perform_destroy(self, instance):
        affected_user = instance.user
        affected_project = instance.group.projectrole.project
        role = instance.group.projectrole.role_type

        if not self.can_manage_roles_for(affected_project):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_project.remove_user(affected_user, role)


class ProjectGroupPermissionViewSet(mixins.CreateModelMixin,
                                    mixins.RetrieveModelMixin,
                                    mixins.ListModelMixin,
                                    mixins.DestroyModelMixin,
                                    viewsets.GenericViewSet):
    """
    Project group permissions expresses connection of users to project groups.
    A single role is supported - Project Group manager.

    Management is done through */api/project-group-permissions/* endpoint.
    """
    # See CustomerPermissionViewSet for implementation details.
    queryset = User.groups.through.objects.exclude(group__projectgrouprole=None)
    serializer_class = serializers.ProjectGroupPermissionSerializer
    permission_classes = (rf_permissions.IsAuthenticated,)
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filter_class = filters.ProjectGroupPermissionFilter

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
                  group__projectgrouprole__project_group__customer__roles__role_type=models.CustomerRole.OWNER) |
                Q(group__projectgrouprole__project_group__projects__roles__permission_group__user=self.request.user) |
                Q(group__projectgrouprole__project_group__roles__permission_group__user=self.request.user)
            ).distinct()

        return queryset

    def list(self, request, *args, **kwargs):
        """
        To list all visible permissions, run a **GET** query against a list.
        Response will contain a list of project groups' users and their brief data.

        To add a new user to the project group, **POST** a new relationship
        to **api/project-permissions** endpoint specifying project, user
        and the role of the user (currently the only role is '1' - project group manager):

        .. code-block:: http

            POST /api/project-permissions/ HTTP/1.1
            Accept: application/json
            Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
            Host: example.com

            {
                "project": "http://example.com/api/projects-groups/6c9b01c251c24174a6691a1f894fae31/",
                "role": "manager",
                "user": "http://example.com/api/users/82cec6c8e0484e0ab1429412fe4194b7/"
            }
        """
        return super(ProjectGroupPermissionViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        To remove a user from a project group, delete corresponding connection (**url** field). Successful deletion
        will return status code 204.

        .. code-block:: http

            DELETE /api/project-group-permissions/42/ HTTP/1.1
            Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
            Host: example.com
        """

        return super(ProjectGroupPermissionViewSet, self).retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        affected_project_group = serializer.validated_data['project_group']
        affected_user = serializer.validated_data['user']

        if not self.can_manage_roles_for(affected_project_group):
            raise PermissionDenied('You do not have permission to perform this action.')

        if not affected_project_group.customer.get_users().filter(pk=affected_user.pk).exists():
            affected_project_group.customer.validate_quota_change({'nc_user_count': 1}, raise_exception=True)

        super(ProjectGroupPermissionViewSet, self).perform_create(serializer)

    def perform_destroy(self, instance):
        affected_user = instance.user
        affected_project_group = instance.group.projectgrouprole.project_group
        role = instance.group.projectgrouprole.role_type

        if not self.can_manage_roles_for(affected_project_group):
            raise PermissionDenied('You do not have permission to perform this action.')

        affected_project_group.remove_user(affected_user, role)


class CustomerPermissionViewSet(mixins.CreateModelMixin,
                                mixins.RetrieveModelMixin,
                                mixins.ListModelMixin,
                                mixins.DestroyModelMixin,
                                viewsets.GenericViewSet):
    """
    - Customers are connected to users through roles, whereas user may have role "customer owner".
    - Each customer may have multiple owners, and each user may own multiple customers.
    - Staff members can list all available customers and create new customers.
      Customer owners can list all customers they own. Customer owners can also create new customers.
    - Project administrators can list all the customers that own any of the projects they are administrators in.
    - Project managers can list all the customers that own any of the projects they are managers in.
    """
    queryset = User.groups.through.objects.exclude(group__customerrole=None)
    serializer_class = serializers.CustomerPermissionSerializer
    permission_classes = (
        rf_permissions.IsAuthenticated,
        # DjangoObjectPermissions not used on purpose, see below.
        # rf_permissions.DjangoObjectPermissions,
    )
    filter_backends = (rf_filters.DjangoFilterBackend,)
    filter_class = filters.CustomerPermissionFilter

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
                  group__customerrole__customer__roles__role_type=models.CustomerRole.OWNER) |
                Q(group__customerrole__customer__projects__roles__permission_group__user=self.request.user) |
                Q(group__customerrole__customer__project_groups__roles__permission_group__user=self.request.user)
            ).distinct()

        return queryset

    def list(self, request, *args, **kwargs):
        """
        Each customer is associated with a group of users that represent customer owners. The link is maintained
        through **api/customer-permissions/** endpoint.

        To list all visible links, run a **GET** query against a list.
        Response will contain a list of customer owners and their brief data.

        To add a new user to the customer, **POST** a new relationship to **customer-permissions** endpoint:

        .. code-block:: http

            POST /api/customer-permissions/ HTTP/1.1
            Accept: application/json
            Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
            Host: example.com

            {
                "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
                "role": "owner",
                "user": "http://example.com/api/users/82cec6c8e0484e0ab1429412fe4194b7/"
            }
        """
        return super(CustomerPermissionViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        To remove a user from a customer owner group, delete corresponding connection (**url** field).
        Successful deletion will return status code 204.

        .. code-block:: http

            DELETE /api/customer-permissions/71/ HTTP/1.1
            Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
            Host: example.com
        """
        return super(CustomerPermissionViewSet, self).retrieve(request, *args, **kwargs)

    # DjangoObjectPermissions is not used because it cannot enforce
    # create permissions based on the body of the request.
    # Another reason is to foster symmetry: check for both granting
    # and revocation are kept in one place - the view.
    def perform_create(self, serializer):
        affected_customer = serializer.validated_data['customer']
        affected_user = serializer.validated_data['user']

        if not self.can_manage_roles_for(affected_customer):
            raise PermissionDenied('You do not have permission to perform this action.')

        if not affected_customer.get_users().filter(pk=affected_user.pk).exists():
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
    """
    Historical information about creation time of projects, project groups and customers.
    """
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

    def list(self, request, *args, **kwargs):
        """
        Available request parameters:

        - ?type=type_of_statistics_objects (required. Have to be from the list: 'customer', 'project', 'project_group')
        - ?from=timestamp (default: now - 30 days, for example: 1415910025)
        - ?to=timestamp (default: now, for example: 1415912625)
        - ?datapoints=how many data points have to be in answer (default: 6)

        Answer will be list of datapoints(dictionaries).
        Each datapoint will contain fields: 'to', 'from', 'value'.
        'Value' - count of objects, that were created between 'from' and 'to' dates.

        Example:

        .. code-block:: javascript

            [
                {"to": 471970877, "from": 1, "value": 5},
                {"to": 943941753, "from": 471970877, "value": 0},
                {"to": 1415912629, "from": 943941753, "value": 3}
            ]
        """
        return super(CreationTimeStatsView, self).list(request, *args, **kwargs)


class SshKeyViewSet(mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.DestroyModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """
    SSH public keys are injected to VM instances during creation, so that holder of corresponding SSH private key can
    log in to that instance.
    SSH public keys are connected to user accounts, whereas the key may belong to one user only,
    and the user may have multiple SSH keys.
    Users can only access SSH keys connected to their accounts. Staff users can see all the accounts.
    Project administrators can select what SSH key will be injected into VM instance during instance provisioning.
    """

    queryset = core_models.SshPublicKey.objects.all()
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'
    filter_backends = (rf_filters.DjangoFilterBackend, core_filters.StaffOrUserFilter)
    filter_class = filters.SshKeyFilter

    def list(self, request, *args, **kwargs):
        """
        To get a list of SSH keys, run **GET** against */api/keys/* as authenticated user.

        A new SSH key can be created by any active users. Example of a valid request:

        .. code-block:: http

            POST /api/keys/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "ssh_public_key1",
                "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDURXDP5YhOQUYoDuTxJ84DuzqMJYJqJ8+SZT28
                               TtLm5yBDRLKAERqtlbH2gkrQ3US58gd2r8H9jAmQOydfvgwauxuJUE4eDpaMWupqquMYsYLB5f+vVGhdZbbzfc6DTQ2rY
                               dknWoMoArlG7MvRMA/xQ0ye1muTv+mYMipnd7Z+WH0uVArYI9QBpqC/gpZRRIouQ4VIQIVWGoT6M4Kat5ZBXEa9yP+9du
                               D2C05GX3gumoSAVyAcDHn/xgej9pYRXGha4l+LKkFdGwAoXdV1z79EG1+9ns7wXuqMJFHM2KDpxAizV0GkZcojISvDwuh
                               vEAFdOJcqjyyH4FOGYa8usP1 jhon@example.com",
            }
        """
        return super(SshKeyViewSet, self).list(request, *args, **kwargs)

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


class ServiceSettingsViewSet(mixins.RetrieveModelMixin,
                             mixins.UpdateModelMixin,
                             mixins.ListModelMixin,
                             viewsets.GenericViewSet):
    queryset = models.ServiceSettings.objects.filter()
    serializer_class = serializers.ServiceSettingsSerializer
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    filter_class = filters.ServiceSettingsFilter
    lookup_field = 'uuid'

    def list(self, request, *args, **kwargs):
        """
        To get a list of service settings, run **GET** against */api/service-settings/* as an authenticated user.
        Only settings owned by this user or shared settings will be listed.

        Supported filters are:

        - ?name=<text> - partial matching used for searching
        - ?type=<type> - choices: OpenStack, DigitalOcean, Amazon, JIRA, GitLab, Oracle
        - ?state=<state> - choices: New, Creation Scheduled, Creating, Sync Scheduled, Syncing, In Sync, Erred
        """
        return super(ServiceSettingsViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        To update service settings, issue a **PUT** or **PATCH** to */api/service-settings/<uuid>/* as a customer owner.
        You are allowed to change name and credentials only.

        Example of a request:

        .. code-block:: http

            PATCH /api/service-settings/9079705c17d64e6aa0af2e619b0e0702/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "username": "admin",
                "password": "new_secret"
            }
        """
        return super(ServiceSettingsViewSet, self).retrieve(request, *args, **kwargs)


class ServiceMetadataViewSet(viewsets.GenericViewSet):
    def list(self, request):
        """
        To get a list of supported service types, run **GET** against */api/service-metadata/* as an authenticated user.
        Use an endpoint from the returned list in order to create new service.
        """
        return Response(SupportedServices.get_services_with_resources(request))


class ResourceViewSet(mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    """
    Use */api/resources/* to get a list of all the resources of any type that a user can see.
    """
    model = models.Resource  # for permissions definition.
    serializer_class = serializers.SummaryResourceSerializer
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, filters.ResourceSummaryFilterBackend, filters.TagsFilter)

    def get_queryset(self):
        resource_models = {k: v for k, v in SupportedServices.get_resource_models().items()
                           if k != 'IaaS.Instance'}
        resource_models = self._filter_by_category(resource_models)
        resource_models = self._filter_by_types(resource_models)

        return managers.SummaryQuerySet(resource_models.values())

    def _filter_by_types(self, resource_models):
        types = self.request.query_params.getlist('resource_type', None)
        if types:
            resource_models = {k: v for k, v in resource_models.items() if k in types}
        return resource_models

    def _filter_by_category(self, resource_models):
        choices = {
            'apps': models.ResourceMixin.get_app_models(),
            'vms': models.ResourceMixin.get_vm_models(),
            'private_clouds': models.ResourceMixin.get_private_cloud_models()
        }
        category = self.request.query_params.get('resource_category')
        category_models = choices.get(category)
        if category_models:
            resource_models = {k: v for k, v in resource_models.items() if v in category_models}
        return resource_models

    def list(self, request, *args, **kwargs):
        """
        To get a list of supported resources' actions, run **OPTIONS** against
        */api/<resource_url>/* as an authenticated user.

        It is possible to filter and order by resource-specific fields, but this filters will be applied only to
        resources that support such filtering. For example it is possible to sort resource by ?o=ram, but SugarCRM crms
        will ignore this ordering, because they do not support such option.

        Filter resources by type or category
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

        There are two query argument to select resources by their type.

        - Specify explicitly list of resource types, for example:

          /api/<resource_endpoint>/?resource_type=DigitalOcean.Droplet&resource_type=OpenStack.Instance

        - Specify category, one of vms, apps or private_clouds, for example:

          /api/<resource_endpoint>/?category=vms

        Filtering by monitoring fields
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

        Resources may have SLA attached to it. Example rendering of SLA:

        .. code-block:: javascript

            "sla": {
                "value": 95.0
                "agreed_value": 99.0,
                "period": "2016-03"
            }

        You may filter or order resources by SLA. Default period is current year and month.

        - Example query for filtering list of resources by actual SLA:

          /api/<resource_endpoint>/?actual_sla=90&period=2016-02

        - Warning! If resource does not have SLA attached to it, it is not included in ordered response.
          Example query for ordering list of resources by actual SLA:

          /api/<resource_endpoint>/?o=actual_sla&period=2016-02

        Service list is displaying current SLAs for each of the items. By default,
        SLA period is set to the current month. To change the period pass it as a query argument:

        - ?period=YYYY-MM - return a list with SLAs for a given month
        - ?period=YYYY - return a list with SLAs for a given year

        In all cases all currently running resources are returned, if SLA for the given period is
        not known or not present, it will be shown as **null** in the response.

        Resources may have monitoring items attached to it. Example rendering of monitoring items:

        .. code-block:: javascript

            "monitoring_items": {
               "application_state": 1
            }

        You may filter or order resources by monitoring item.

        - Example query for filtering list of resources by installation state:

          /api/<resource_endpoint>/?monitoring__installation_state=1

        - Warning! If resource does not have monitoring item attached to it, it is not included in ordered response.
          Example query for ordering list of resources by installation state:

          /api/<resource_endpoint>/?o=monitoring__installation_state

        Filtering by tags
        ^^^^^^^^^^^^^^^^^

        Resource may have tags attached to it. Example of tags rendering:

        .. code-block:: javascript

            "tags": [
                "license-os:centos7",
                "os-family:linux",
                "license-application:postgresql",
                "support:premium"
            ]

        Tags filtering:

         - ?tag=IaaS - filter by full tag name, using method OR. Can be list.
         - ?rtag=os-family:linux - filter by full tag name, using AND method. Can be list.
         - ?tag__license-os=centos7 - filter by tags with particular prefix.

        Tags ordering:

         - ?o=tag__license-os - order by tag with particular prefix. Instances without given tag will not be returned.
        """

        return super(ResourceViewSet, self).list(request, *args, **kwargs)

    @list_route()
    def count(self, request):
        """
        Count resources by type. Example output:

        .. code-block:: javascript

            {
                "Amazon.Instance": 0,
                "GitLab.Project": 3,
                "Azure.VirtualMachine": 0,
                "DigitalOcean.Droplet": 0,
                "OpenStack.Instance": 0,
                "GitLab.Group": 8
            }
        """
        queryset = self.filter_queryset(self.get_queryset())
        return Response({SupportedServices.get_name_for_model(qs.model): qs.count()
                         for qs in queryset.querysets})


class ServicesViewSet(BaseSummaryView):
    """ The summary list of all user services. """

    params = filters.BaseServiceFilter.Meta.fields

    def get_urls(self, request):
        return SupportedServices.get_services(request).values()


class CounterMixin(object):
    def get_count(self, url, params):
        response = request_api(self.request, url, method='HEAD', params=params)
        if response.ok:
            return response.total
        else:
            logger.warning('Unable to execute API request with URL %s and error %s', url, response.data)
        return 0


class CustomerCountersView(CounterMixin, viewsets.GenericViewSet):
    """
    Count number of entities related to customer

    .. code-block:: javascript

        {
            "alerts": 12,
            "vms": 1,
            "apps": 0,
            "private_clouds": 1,
            "services": 1,
            "projects": 1,
            "users": 3
        }
    """
    lookup_field = 'uuid'

    def get_queryset(self):
        return filter_queryset_for_user(models.Customer.objects.all().only('pk', 'uuid'), self.request.user)

    def list(self, request, uuid):
        self.customer = self.get_object()

        return Response({
            'alerts': self.get_alerts(),
            'vms': self.get_vms(),
            'apps': self.get_apps(),
            'private_clouds': self.get_private_clouds(),
            'projects': self.get_projects(),
            'services': self.get_services(),
            'users': self.customer.get_users().count()
        })

    def get_alerts(self):
        return self.get_count('alert-list', {
            'aggregate': 'customer',
            'uuid': self.customer.uuid.hex,
            'exclude_features': self.request.query_params.getlist('exclude_features'),
            'opened': True
        })

    def get_vms(self):
        return self._total_count(models.ResourceMixin.get_vm_models())

    def get_apps(self):
        return self._total_count(models.ResourceMixin.get_app_models())

    def get_private_clouds(self):
        return self._total_count(models.ResourceMixin.get_private_cloud_models())

    def get_projects(self):
        return self._count_model(models.Project)

    def get_services(self):
        models = [item['service'] for item in SupportedServices.get_service_models().values()]
        return self._total_count(models)

    def _total_count(self, models):
        return sum(self._count_model(model) for model in models)

    def _count_model(self, model):
        qs = model.objects.filter(customer=self.customer).only('pk')
        qs = filter_queryset_for_user(qs, self.request.user)
        return qs.count()


class ProjectCountersView(CounterMixin, viewsets.GenericViewSet):
    """
    Count number of entities related to project

    .. code-block:: javascript

        {
            "users": 0,
            "alerts": 2,
            "apps": 0,
            "vms": 1,
            "private_clouds": 1,
            "premium_support_contracts": 0,
        }
    """
    lookup_field = 'uuid'

    def get_queryset(self):
        return filter_queryset_for_user(models.Project.objects.all().only('pk', 'uuid'), self.request.user)

    def list(self, request, uuid):
        self.project = self.get_object()
        self.project_uuid = self.project.uuid.hex
        self.exclude_features = request.query_params.getlist('exclude_features')

        return Response({
            'alerts': self.get_alerts(),
            'vms': self.get_vms(),
            'apps': self.get_apps(),
            'private_clouds': self.get_private_clouds(),
            'users': self.get_users(),
            'premium_support_contracts': self.get_premium_support_contracts()
        })

    def get_alerts(self):
        return self.get_count('alert-list', {
            'aggregate': 'project',
            'uuid': self.project_uuid,
            'exclude_features': self.exclude_features,
            'opened': True
        })

    def get_vms(self):
        return self._total_count(models.ResourceMixin.get_vm_models())

    def get_apps(self):
        return self._total_count(models.ResourceMixin.get_app_models())

    def get_private_clouds(self):
        return self._total_count(models.ResourceMixin.get_private_cloud_models())

    def get_users(self):
        return self.get_count('user-list', {
            'project': self.project_uuid
        })

    def get_premium_support_contracts(self):
        return self.get_count('premium-support-contract-list', {
            'project_uuid': self.project_uuid
        })

    def _total_count(self, models):
        return sum(self._count_model(model) for model in models)

    def _count_model(self, model):
        qs = model.objects.filter(project=self.project).only('pk')
        qs = filter_queryset_for_user(qs, self.request.user)
        return qs.count()


class UserCountersView(CounterMixin, viewsets.GenericViewSet):
    """
    Count number of entities related to current user

    .. code-block:: javascript

        {
            "keys": 1,
            "hooks": 1
        }
    """
    def list(self, request):
        self.user_uuid = request.user.uuid.hex

        return Response({
            'keys': self.get_keys(),
            'hooks': self.get_hooks()
        })

    def get_keys(self):
        return self.get_count('sshpublickey-list', {
            'user_uuid': self.user_uuid
        })

    def get_hooks(self):
        return self.get_count('hooks-list', {})


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
    filter_class = filters.BaseServiceFilter
    lookup_field = 'uuid'

    def list(self, request, *args, **kwargs):
        """
        To list all services without regard to its type, run **GET** against */api/services/* as an authenticated user.

        To list services of specific type issue **GET** to specific endpoint from a list above as a customer owner.
        Individual endpoint used for every service type.

        To create a service, issue a **POST** to specific endpoint from a list above as a customer owner.
        Individual endpoint used for every service type.

        You can create service based on shared service settings. Example:

        .. code-block:: http

            POST /api/digitalocean/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "Common DigitalOcean",
                "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
                "settings": "http://example.com/api/service-settings/93ba615d6111466ebe3f792669059cb4/"
            }

        Or provide your own credentials. Example:

        .. code-block:: http

            POST /api/oracle/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "name": "My Oracle",
                "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
                "backend_url": "https://oracle.example.com:7802/em",
                "username": "admin",
                "password": "secret"
            }
        """
        return super(BaseServiceViewSet, self).list(request, *args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        queryset = super(BaseServiceViewSet, self).get_queryset(*args, **kwargs)
        if self.action in ('list', 'retrieve'):
            serializer_class = self.get_serializer_class()
            if hasattr(serializer_class, 'eager_load'):
                return serializer_class.eager_load(queryset)
        return queryset

    def _can_import(self):
        return self.import_serializer_class is not NotImplemented

    def get_serializer_class(self):
        serializer = super(BaseServiceViewSet, self).get_serializer_class()
        if self.action == 'link':
            serializer = self.import_serializer_class if self._can_import() else rf_serializers.Serializer

        return serializer

    def get_serializer_context(self):
        context = super(BaseServiceViewSet, self).get_serializer_context()
        if self.action == 'link':
            context['service'] = self.get_object()
        return context

    def get_import_context(self):
        return {}

    @detail_route()
    def managed_resources(self, request, uuid=None):
        service = self.get_object()
        backend = self.get_backend(service)

        try:
            resources = backend.get_managed_resources()
        except ServiceBackendNotImplemented:
            resources = []

        serializer = serializers.ManagedResourceSerializer(resources, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @detail_route(methods=['get', 'post'])
    def link(self, request, uuid=None):
        """
        To get a list of resources available for import, run **GET** against */<service_endpoint>/link/*
        as an authenticated user.
        Optionally project_uuid parameter can be supplied for services requiring it like OpenStack.

        To import (link with NodeConductor) resource issue **POST** against the same endpoint with resource id.

        .. code-block:: http

            POST /api/openstack/08039f01c9794efc912f1689f4530cf0/link/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "backend_id": "bd5ec24d-9164-440b-a9f2-1b3c807c5df3",
                "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/"
            }
        """
        if not self._can_import():
            raise MethodNotAllowed('link')

        service = self.get_object()
        if service.settings.shared and not request.user.is_staff:
            raise PermissionDenied("Only staff users are allowed to import resources from shared services.")

        if self.request.method == 'GET':
            try:
                backend = self.get_backend(service)
                try:
                    resources = backend.get_resources_for_import(**self.get_import_context())
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
                resource = serializer.save()
            except ServiceBackendError as e:
                raise APIException(e)

            resource_imported.send(sender=resource.__class__, instance=resource)

            return Response(serializer.data, status=status.HTTP_200_OK)

    def get_backend(self, service):
        # project_uuid can be supplied in order to get a list of resources
        # available for import (link) based on project, depends on backend implementation
        project_uuid = self.request.query_params.get('project_uuid')
        if project_uuid:
            spl_class = SupportedServices.get_related_models(service)['service_project_link']
            try:
                spl = spl_class.objects.get(project__uuid=project_uuid, service=service)
            except:
                raise NotFound("Can't find project %s" % project_uuid)
            else:
                return spl.get_backend()
        else:
            return service.get_backend()


class BaseServiceProjectLinkViewSet(UpdateOnlyByPaidCustomerMixin,
                                    core_mixins.UpdateOnlyStableMixin,
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
    filter_class = filters.BaseServiceProjectLinkFilter

    def list(self, request, *args, **kwargs):
        """
        To get a list of connections between a project and an service, run **GET** against service_project_link_url
        as authenticated user. Note that a user can only see connections of a project where a user has a role.

        If service has `available_for_all` flag, project-service connections are created automatically.
        Otherwise, in order to be able to provision resources, service must first be linked to a project.
        To do that, **POST** a connection between project and a service to service_project_link_url
        as stuff user or customer owner.
        """
        return super(BaseServiceProjectLinkViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        To remove a link, issue **DELETE** to URL of the corresponding connection as stuff user or customer owner.
        """
        return super(BaseServiceProjectLinkViewSet, self).retrieve(request, *args, **kwargs)


def safe_operation(valid_state=None):
    def decorator(view_fn):
        view_fn.valid_state = valid_state

        @functools.wraps(view_fn)
        def wrapped(self, request, *args, **kwargs):
            message = "Performing %s operation is not allowed for resource in its current state"
            operation_name = view_fn.__name__

            try:
                with transaction.atomic():
                    resource = self.get_object()
                    check_operation(request.user, resource, operation_name, valid_state)

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

            if resource.pk is None:
                return Response(status=status.HTTP_204_NO_CONTENT)

            return Response({'status': '%s was scheduled' % operation_name},
                            status=status.HTTP_202_ACCEPTED)

        return wrapped
    return decorator


class ResourceViewMetaclass(type):
    """ Store view in registry """
    def __new__(cls, name, bases, args):
        resource_view = super(ResourceViewMetaclass, cls).__new__(cls, name, bases, args)
        queryset = args.get('queryset')
        if hasattr(queryset, 'model'):
            SupportedServices.register_resource_view(queryset.model, resource_view)
        return resource_view


class ResourceViewMixin(UpdateOnlyByPaidCustomerMixin):
    class PaidControl:
        customer_path = 'service_project_link__service__customer'
        settings_path = 'service_project_link__service__settings'

    queryset = NotImplemented
    serializer_class = NotImplemented
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (
        filters.GenericRoleFilter,
        core_filters.DjangoMappingFilterBackend,
        SlaFilter,
        MonitoringItemFilter,
        filters.TagsFilter,
        filters.StartTimeFilter
    )
    metadata_class = ResourceActionsMetadata


class _BaseResourceViewSet(six.with_metaclass(ResourceViewMetaclass,
                                              ResourceViewMixin,
                                              core_mixins.UserContextMixin,
                                              viewsets.ModelViewSet)):
    filter_class = filters.BaseResourceFilter

    def retrieve(self, request, *args, **kwargs):
        """
        Optional `field` query parameter (can be list) allows to limit what fields are returned.
        For example, given request /api/openstack-instances/<uuid>/?field=uuid&field=name you get response like this:

        .. code-block:: javascript

            {
                "uuid": "90bcfe38b0124c9bbdadd617b5d739f5",
                "name": "Azure Virtual Machine"
            }
        """
        return super(_BaseResourceViewSet, self).retrieve(request, *args, **kwargs)

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

        super(_BaseResourceViewSet, self).initial(request, *args, **kwargs)

    def perform_create(self, serializer):
        service_project_link = serializer.validated_data['service_project_link']

        if service_project_link.service.settings.state == core_models.SynchronizationStates.ERRED:
            raise core_exceptions.IncorrectStateException(
                detail='Cannot create resource if its service is in erred state.')

        try:
            self.perform_provision(serializer)
        except ServiceBackendError as e:
            raise APIException(e)

        event_logger.resource.info(
            '{resource_full_name} creation has been scheduled.',
            event_type='resource_creation_scheduled',
            event_context={'resource': serializer.instance})

    def perform_update(self, serializer):
        old_name = serializer.instance.name
        resource = serializer.save()

        message = '{resource_full_name} has been updated.'
        if old_name != resource.name:
            message += ' Name was changed from %s to %s.' % (old_name, resource.name)

        event_logger.resource.info(
            message,
            event_type='resource_update_succeeded',
            event_context={'resource': resource})

    def perform_destroy(self, resource):
        resource.delete()
        event_logger.resource.info(
            '{resource_full_name} has been deleted.',
            event_type='resource_deletion_succeeded',
            event_context={'resource': resource})

    def perform_provision(self, serializer):
        raise NotImplementedError

    def perform_managed_resource_destroy(self, resource, force=False):
        if resource.backend_id:
            backend = resource.get_backend()
            backend.destroy(resource, force=force)
            event_logger.resource.info(
                '{resource_full_name} has been scheduled for deletion.',
                event_type='resource_deletion_scheduled',
                event_context={'resource': resource})
        else:
            self.perform_destroy(resource)

    @detail_route(methods=['post'])
    @safe_operation()
    def unlink(self, request, resource, uuid=None):
        # XXX: add special attribute to an instance in order to be tracked by signal handler
        setattr(resource, 'PERFORM_UNLINK', True)
        self.perform_destroy(resource)
    unlink.destructive = True


# TODO: Consider renaming to BaseVirtualMachineViewSet
class BaseResourceViewSet(_BaseResourceViewSet):
    @safe_operation(valid_state=(models.Resource.States.OFFLINE, models.Resource.States.ERRED))
    def destroy(self, request, resource, uuid=None):
        self.perform_managed_resource_destroy(
            resource, force=resource.state == models.Resource.States.ERRED)

    @detail_route(methods=['post'])
    @safe_operation(valid_state=models.Resource.States.OFFLINE)
    def start(self, request, resource, uuid=None):
        """
        Schedule resource start. Resource must be in OFFLINE state.
        """
        backend = resource.get_backend()
        backend.start(resource)
        event_logger.resource.info(
            'Resource {resource_name} has been scheduled to start.',
            event_type='resource_start_scheduled',
            event_context={'resource': resource})

    @detail_route(methods=['post'])
    @safe_operation(valid_state=models.Resource.States.ONLINE)
    def stop(self, request, resource, uuid=None):
        """
        Schedule resource stop. Resource must be in ONLINE state.
        """
        backend = resource.get_backend()
        backend.stop(resource)
        event_logger.resource.info(
            'Resource {resource_name} has been scheduled to stop.',
            event_type='resource_stop_scheduled',
            event_context={'resource': resource})

    @detail_route(methods=['post'])
    @safe_operation(valid_state=models.Resource.States.ONLINE)
    def restart(self, request, resource, uuid=None):
        """
        Schedule resource restart. Resource must be in ONLINE state.
        """
        backend = resource.get_backend()
        backend.restart(resource)
        event_logger.resource.info(
            'Resource {resource_name} has been scheduled to restart.',
            event_type='resource_restart_scheduled',
            event_context={'resource': resource})


class BaseOnlineResourceViewSet(_BaseResourceViewSet):

    # User can only create and delete this resource. He cannot stop them.
    @safe_operation(valid_state=[models.Resource.States.ONLINE, models.Resource.States.ERRED])
    def destroy(self, request, resource, uuid=None):
        if resource.state == models.Resource.States.ONLINE:
            resource.state = resource.States.OFFLINE
            resource.save()
        self.perform_managed_resource_destroy(resource, force=resource.state == models.Resource.States.ERRED)

    destroy.method = 'DELETE'
    destroy.destructive = True


class BaseResourceExecutorViewSet(six.with_metaclass(ResourceViewMetaclass,
                                                     StateExecutorViewSet,
                                                     core_mixins.UserContextMixin,
                                                     viewsets.ModelViewSet)):

    queryset = NotImplemented
    serializer_class = NotImplemented
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (
        filters.GenericRoleFilter,
        core_filters.DjangoMappingFilterBackend,
        SlaFilter,
        MonitoringItemFilter,
        filters.TagsFilter,
    )
    filter_class = filters.BaseResourceStateFilter
    metadata_class = ResourceActionsMetadata
    create_executor = NotImplemented
    update_executor = NotImplemented
    delete_executor = NotImplemented


class BaseServicePropertyViewSet(viewsets.ReadOnlyModelViewSet):
    filter_class = filters.BaseServicePropertyFilter


class BaseResourcePropertyExecutorViewSet(core_mixins.CreateExecutorMixin,
                                          core_mixins.UpdateExecutorMixin,
                                          core_mixins.DeleteExecutorMixin,
                                          viewsets.ModelViewSet):
    queryset = NotImplemented
    serializer_class = NotImplemented
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)
    filter_backends = (filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)


class AggregatedStatsView(views.APIView):
    """
    Quotas and quotas usage aggregated by projects/project_groups/customers.

    Available request parameters:
        - ?aggregate=aggregate_model_name (default: 'customer'.
          Have to be from list: 'customer', 'project', 'project_group')
        - ?uuid=uuid_of_aggregate_model_object (not required. If this parameter will be defined -
          result will contain only object with given uuid)
        - ?quota_name - optional list of quota names, for example ram, vcpu, storage
    """
    def get(self, request, format=None):
        serializer = serializers.AggregateSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        quota_names = request.query_params.getlist('quota_name')
        if len(quota_names) == 0:
            quota_names = None
        querysets = serializer.get_service_project_links(request.user)

        total_sum = QuotaModelMixin.get_sum_of_quotas_for_querysets(querysets, quota_names)
        total_sum = sort_dict(total_sum)
        return Response(total_sum, status=status.HTTP_200_OK)


class QuotaTimelineStatsView(views.APIView):
    """
    Historical data of quotas and quotas usage aggregated by projects/project_groups/customers.

    Available request parameters:

    - ?from=timestamp (default: now - 1 day, for example: 1415910025)
    - ?to=timestamp (default: now, for example: 1415912625)
    - ?interval (default: day. Has to be from list: hour, day, week, month)
    - ?item=<quota_name>. If this parameter is not defined - endpoint will return data for all items.
    - ?aggregate=aggregate_model_name (default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
    - ?uuid=uuid_of_aggregate_model_object (not required. If this parameter is defined, result will contain only object with given uuid)

    Answer will be list of dictionaries with fields, determining time frame. It's size is equal to interval parameter.
    Values within each bucket are averaged for each project and then all projects metrics are summarized.

    Value fields include:

    - vcpu_limit - virtual CPUs quota
    - vcpu_usage - virtual CPUs usage
    - ram_limit - RAM quota limit, in MiB
    - ram_usage - RAM usage, in MiB
    - storage_limit - volume storage quota limit, in MiB
    - storage_usage - volume storage quota consumption, in MiB
    """

    def get(self, request, format=None):
        scopes = self.get_quota_scopes(request)
        ranges = self.get_ranges(request)
        items = request.query_params.getlist('item') or self.get_all_spls_quotas()

        collector = QuotaTimelineCollector()
        for item in items:
            for scope in scopes:
                values = self.get_stats_for_scope(item, scope, ranges)
                for (end, start), (limit, usage) in zip(ranges, values):
                    collector.add_quota(start, end, item, limit, usage)

        stats = map(sort_dict, collector.to_dict())[::-1]
        return Response(stats, status=status.HTTP_200_OK)

    def get_quota_scopes(self, request):
        serializer = serializers.AggregateSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        scopes = sum([list(qs) for qs in serializer.get_service_project_links(request.user)], [])
        return scopes

    def get_all_spls_quotas(self):
        spl_models = [m for m in models.ServiceProjectLink.get_all_models()]
        return sum([spl_model.get_quotas_names() for spl_model in spl_models], [])

    def get_stats_for_scope(self, quota_name, scope, dates):
        stats_data = []
        try:
            quota = scope.quotas.get(name=quota_name)
        except Quota.DoesNotExist:
            return stats_data
        versions = reversion\
            .get_for_object(quota)\
            .select_related('revision')\
            .filter(revision__date_created__lte=dates[0][0])\
            .iterator()
        version = None
        for end, start in dates:
            try:
                while version is None or version.revision.date_created > end:
                    version = versions.next()
                stats_data.append((version.object_version.object.limit,
                                   version.object_version.object.usage))
            except StopIteration:
                break

        return stats_data

    def get_ranges(self, request):
        mapped = {
            'start_time': request.query_params.get('from'),
            'end_time': request.query_params.get('to'),
            'interval': request.query_params.get('interval')
        }
        data = {key: val for (key, val) in mapped.items() if val}

        serializer = core_serializers.TimelineSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        date_points = serializer.get_date_points()
        reversed_dates = date_points[::-1]
        ranges = zip(reversed_dates[:-1], reversed_dates[1:])
        return ranges


class QuotaTimelineCollector(object):
    """
    Helper class for QuotaTimelineStatsView.
    Aggregate quotas grouped by date range and quota name.
    Example output rendering:

    .. code-block:: javascript

        [
            {
                "from": start,
                "to" end,
                "vcpu_limit": 10,
                "vcpu_usage": 5,
                "ram_limit": 4000,
                "ran_usage": 1000
            }
        ]
    """
    def __init__(self):
        self.ranges = set()
        self.items = set()
        self.limits = defaultdict(int)
        self.usages = defaultdict(int)

    def add_quota(self, start, end, item, limit, usage):
        key = (start, end, item)
        if limit == -1 or self.limits[key] == -1:
            self.limits[key] = -1
        else:
            self.limits[key] += limit
        self.usages[key] += usage
        self.ranges.add((start, end))
        self.items.add(item)

    def to_dict(self):
        table = []
        for start, end in sorted(self.ranges):
            row = {
                'from': datetime_to_timestamp(start),
                'to': datetime_to_timestamp(end)
            }
            for item in sorted(self.items):
                key = (start, end, item)
                row['%s_limit' % item] = self.limits[key]
                row['%s_usage' % item] = self.usages[key]
            table.append(row)
        return table
