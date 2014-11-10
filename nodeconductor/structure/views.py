from __future__ import unicode_literals

from django.contrib import auth
from django.db.models.query_utils import Q
import django_filters
from rest_framework import filters as rf_filter
from rest_framework import mixins as rf_mixins
from rest_framework import permissions as rf_permissions
from rest_framework import status
from rest_framework import viewsets as rf_viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.settings import api_settings

from nodeconductor.core import permissions
from nodeconductor.core import viewsets
from nodeconductor.core import mixins
from nodeconductor.structure import filters
from nodeconductor.structure import models
from nodeconductor.structure import serializers
from nodeconductor.structure.models import ProjectRole, CustomerRole, ProjectGroupRole


User = auth.get_user_model()


class CustomerViewSet(viewsets.ModelViewSet):
    """List of customers that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#customer-management
    """

    queryset = models.Customer.objects.all()
    serializer_class = serializers.CustomerSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def pre_delete(self, obj):
        projects = models.Project.objects.filter(customer=obj).exists()
        if projects:
            raise PermissionDenied('Cannot delete customer with existing projects')

        project_groups = models.ProjectGroup.objects.filter(customer=obj).exists()
        if project_groups:
            raise PermissionDenied('Cannot delete customer with existing project_groups')


class ProjectFilter(django_filters.FilterSet):
    project_group = django_filters.CharFilter(
        name='project_groups__uuid',
        distinct=True,
    )
    name = django_filters.CharFilter(lookup_type='icontains')

    vcpu = django_filters.NumberFilter(
        name='resource_quota__vcpu',
    )

    ram = django_filters.NumberFilter(
        name='resource_quota__ram',
    )

    storage = django_filters.NumberFilter(
        name='resource_quota__storage',
    )

    max_instances = django_filters.NumberFilter(
        name='resource_quota__max_instances',
    )

    class Meta(object):
        model = models.Project
        fields = [
            'project_group',
            'name',
            'vcpu',
            'ram',
            'storage',
            'max_instances'
        ]
        order_by = [
            'name',
            '-name',
            'resource_quota__vcpu',
            '-resource_quota__vcpu',
            'resource_quota__ram',
            '-resource_quota__ram',
            'resource_quota__storage',
            '-resource_quota__storage',
            'resource_quota__max_instances',
            '-resource_quota__max_instances'
        ]


class ProjectViewSet(viewsets.ModelViewSet):
    """List of projects that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#project-management
    """

    queryset = models.Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, rf_filter.DjangoFilterBackend,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)
    filter_class = ProjectFilter

    def get_queryset(self):
        user = self.request.user
        queryset = super(ProjectViewSet, self).get_queryset()

        can_manage = self.request.QUERY_PARAMS.get('can_manage', None)
        if can_manage is not None:
            #XXX: Let the DB cry...
            queryset = queryset.filter(
                Q(customer__roles__permission_group__user=user,
                  customer__roles__role_type=models.CustomerRole.OWNER)
                |
                Q(roles__permission_group__user=user,
                  roles__role_type=models.ProjectRole.MANAGER)
            ).distinct()

        return queryset

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.ProjectCreateSerializer

        return super(ProjectViewSet, self).get_serializer_class()


class ProjectGroupFilter(django_filters.FilterSet):
    customer = django_filters.CharFilter(
        name='customer__name',
        distinct=True,
        lookup_type='icontains',
    )

    name = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = models.ProjectGroup
        fields = [
            'name',
            'customer',
        ]
        order_by = [
            'name',
            '-name',
            'customer__name',
            '-customer__name',
        ]


class ProjectGroupViewSet(viewsets.ModelViewSet):
    """
    List of project groups that are accessible to this user.

    TODO: add documentation
    """

    queryset = models.ProjectGroup.objects.all()
    serializer_class = serializers.ProjectGroupSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter, rf_filter.DjangoFilterBackend,)
    # permission_classes = (permissions.IsAuthenticated,)  # TODO: Add permissions for Create/Update
    filter_class = ProjectGroupFilter


class ProjectGroupMembershipViewSet(rf_mixins.CreateModelMixin,
                                    rf_mixins.RetrieveModelMixin,
                                    rf_mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    rf_viewsets.GenericViewSet):
    """List of project groups members that are accessible by this user.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#managing-project-roles
    """

    queryset = models.ProjectGroup.projects.through.objects.all()
    serializer_class = serializers.ProjectGroupMembershipSerializer
    filter_backends = (filters.GenericRoleFilter,)

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
    native_name = django_filters.CharFilter(lookup_type='icontains')
    organization = django_filters.CharFilter(lookup_type='icontains')
    job_title = django_filters.CharFilter(lookup_type='icontains')
    # XXX: temporary. Should be done by a proper search full-text search engine
    description = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = User
        fields = [
            'full_name',
            'native_name',
            'organization',
            'email',
            'phone_number',
            'description',
            'job_title',
            'project',
            'project_group',
            'username',
        ]
        order_by = [
            'full_name',
            'native_name',
            'organization',
            'email',
            'phone_number',
            'description',
            'job_title',
            'username',
        ]


class UserViewSet(viewsets.ModelViewSet):
    """
    List of NodeConductor users.

    http://nodeconductor.readthedocs.org/en/latest/api/api.html#user-management
    """

    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated, permissions.IsAdminOrReadOnly)
    filter_class = UserFilter

    def get_queryset(self):
        user = self.request.user
        queryset = super(UserViewSet, self).get_queryset()
        # TODO: refactor against django filtering

        civil_number = self.request.QUERY_PARAMS.get('civil_number', None)
        if civil_number is not None:
            queryset = queryset.filter(civil_number=civil_number)

        current_user = self.request.QUERY_PARAMS.get('current', None)
        if current_user is not None and not user.is_anonymous():
            queryset = User.objects.filter(uuid=user.uuid)

        # TODO: refactor to a separate endpoint or structure
        # a special query for all users with assigned privileges that the current user can remove privileges from
        can_manage = self.request.QUERY_PARAMS.get('can_manage', None)
        if can_manage is not None:
            #XXX: Let the DB cry...
            queryset = queryset.filter(
                Q(groups__customerrole__customer__roles__permission_group__user=user,
                  groups__customerrole__customer__roles__role_type=models.CustomerRole.OWNER)
                |
                Q(groups__projectrole__project__roles__permission_group__user=user,
                  groups__projectrole__project__roles__role_type=models.ProjectRole.MANAGER)
            ).distinct()

        return queryset


class ProjectPermissionViewSet(rf_mixins.RetrieveModelMixin,
                               mixins.ListModelMixin,
                               rf_viewsets.GenericViewSet):
    queryset = User.groups.through.objects.exclude(group__projectrole=None)
    serializer_class = serializers.ProjectPermissionSerializer
    filter_backends = (filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def can_save(self, user_group):
        user = self.request.user
        project = user_group.group.projectrole.project

        if project.has_user(user, ProjectRole.MANAGER):
            return True

        if project.customer.has_user(user, CustomerRole.OWNER):
            return True
        
        # TODO: Move to ProjectGroup.has_user()
        is_group_manager = project.project_groups.filter(
            roles__permission_group__user=user, roles__role_type=ProjectGroupRole.MANAGER).exists()
        if is_group_manager:
            return True

        return False

    def get_queryset(self):
        queryset = super(ProjectPermissionViewSet, self).get_queryset()

        # TODO: refactor against django filtering
        user_uuid = self.request.QUERY_PARAMS.get('user', None)
        if user_uuid is not None:
            queryset = queryset.filter(user__uuid=user_uuid)

        return queryset

    def get_success_headers(self, data):
        try:
            return {'Location': data[api_settings.URL_FIELD_NAME]}
        except (TypeError, KeyError):
            return {}

    def pre_save(self, obj):
        if not self.can_save(obj):
            raise PermissionDenied()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)

        if serializer.is_valid():
            self.pre_save(serializer.object)

            project = serializer.object.group.projectrole.project
            user = serializer.object.user
            role = serializer.object.group.projectrole.role_type

            self.object, created = project.add_user(user, role)

            self.post_save(self.object, created=created)

            # Instantiating serializer again, this time with instance
            # to make urls render properly.
            serializer = self.get_serializer(instance=self.object)

            headers = self.get_success_headers(serializer.data)

            if created:
                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED,
                    headers=headers,
                )
            else:
                return Response(
                    {'detail': 'Permissions were not modified'},
                    status=status.HTTP_304_NOT_MODIFIED,
                    headers=headers,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        self.pre_delete(obj)

        user = obj.user
        project = obj.group.projectrole.project
        role = obj.group.projectrole.role_type

        project.remove_user(user, role)

        self.post_delete(obj)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectGroupPermissionViewSet(rf_mixins.CreateModelMixin,
                                    rf_mixins.RetrieveModelMixin,
                                    rf_mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    rf_viewsets.GenericViewSet):
    queryset = User.groups.through.objects.all()
    serializer_class = serializers.ProjectGroupPermissionSerializer
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def get_queryset(self):
        queryset = super(ProjectGroupPermissionViewSet, self).get_queryset()
        queryset = queryset.exclude(group__projectgrouprole=None)

        # TODO: refactor against django filtering
        user_uuid = self.request.QUERY_PARAMS.get('user', None)
        if user_uuid is not None:
            queryset = queryset.filter(user__uuid=user_uuid)

        # TODO: Test for it!
        # XXX: This should be removed after permissions refactoring
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(group__projectgrouprole__project_group__customer__roles__permission_group__user=self.request.user,
                  group__projectgrouprole__project_group__customer__roles__role_type=models.CustomerRole.OWNER)
                |
                Q(group__projectgrouprole__project_group__projects__roles__permission_group__user=self.request.user,
                  group__projectgrouprole__project_group__customer__roles__role_type=models.ProjectRole.MANAGER)
                |
                Q(group__projectgrouprole__project_group__roles__permission_group__user=self.request.user)
            ).distinct()

        return queryset

    def pre_save(self, obj):
        super(ProjectGroupPermissionViewSet, self).pre_save(obj)
        user = self.request.user
        project_group = obj.group.projectgrouprole.project_group

        # check for the user role. Inefficient but more readable
        is_customer_owner = project_group.customer.roles.filter(
            permission_group__user=user, role_type=CustomerRole.OWNER).exists()
        if is_customer_owner:
            return

        is_group_manager = project_group.project_groups.filter(
            roles__permission_group__user=user, roles__role_type=ProjectGroupRole.MANAGER).exists()
        if is_group_manager:
            return

        raise PermissionDenied()


class CustomerPermissionFilter(django_filters.FilterSet):
    customer = django_filters.CharFilter(
        name='group__customerrole__customer__uuid',
    )
    username = django_filters.CharFilter(
        name='user__username',
    )
    full_name = django_filters.CharFilter(
        name='user__full_name',
    )
    native_name = django_filters.CharFilter(
        name='user__native_name',
    )

    class Meta(object):
        model = User.groups.through
        fields = [
            'customer',
            'username',
            'full_name',
            'native_name',
        ]


class CustomerPermissionViewSet(rf_mixins.RetrieveModelMixin,
                                mixins.ListModelMixin,
                                rf_viewsets.GenericViewSet):
    queryset = User.groups.through.objects.exclude(group__customerrole=None)
    serializer_class = serializers.CustomerPermissionSerializer
    filter_backends = (rf_filter.DjangoFilterBackend,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)
    filter_class = CustomerPermissionFilter

    def can_save(self, user_group):
        user = self.request.user
        customer = user_group.group.customerrole.customer

        if customer.has_user(user, CustomerRole.OWNER):
            return True

        return False

    def get_queryset(self):
        queryset = super(CustomerPermissionViewSet, self).get_queryset()

        # TODO: Test for it!
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

    def get_success_headers(self, data):
        try:
            return {'Location': data[api_settings.URL_FIELD_NAME]}
        except (TypeError, KeyError):
            return {}

    def pre_save(self, obj):
        if not self.can_save(obj):
            raise PermissionDenied()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.DATA, files=request.FILES)

        if serializer.is_valid():
            self.pre_save(serializer.object)

            customer = serializer.object.group.customerrole.customer
            user = serializer.object.user
            role = serializer.object.group.customerrole.role_type

            self.object, created = customer.add_user(user, role)

            self.post_save(self.object, created=created)

            # Instantiating serializer again, this time with instance
            # to make urls render properly.
            serializer = self.get_serializer(instance=self.object)

            headers = self.get_success_headers(serializer.data)

            if created:
                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED,
                    headers=headers,
                )
            else:
                return Response(
                    {'detail': 'Permissions were not modified'},
                    status=status.HTTP_304_NOT_MODIFIED,
                    headers=headers,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        self.pre_delete(obj)

        user = obj.user
        customer = obj.group.customerrole.customer
        role = obj.group.customerrole.role_type

        customer.remove_user(user, role)

        self.post_delete(obj)

        return Response(status=status.HTTP_204_NO_CONTENT)

# XXX: This should be put to models
filters.set_permissions_for_model(
    User.groups.through,
    customer_path='group__projectrole__project__customer',
    project_path='group__projectrole__project',
)
