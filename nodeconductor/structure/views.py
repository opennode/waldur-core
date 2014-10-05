from __future__ import unicode_literals

from django.contrib import auth
from django.db.models.query_utils import Q
import django_filters
from rest_framework import mixins as rf_mixins
from rest_framework import permissions as rf_permissions
from rest_framework import viewsets as rf_viewsets
from rest_framework.exceptions import PermissionDenied

from nodeconductor.core import permissions
from nodeconductor.core import viewsets
from nodeconductor.core import mixins
from nodeconductor.structure import filters
from nodeconductor.structure import models
from nodeconductor.structure import serializers
from nodeconductor.structure.models import ProjectRole, CustomerRole


User = auth.get_user_model()


class CustomerViewSet(viewsets.ModelViewSet):
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


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = models.Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def get_queryset(self):
        user = self.request.user
        queryset = super(ProjectViewSet, self).get_queryset()

        can_manage = self.request.QUERY_PARAMS.get('can_manage', None)
        if can_manage is not None:
            queryset = queryset.filter(roles__permission_group__user=user,
                                       roles__role_type=models.ProjectRole.MANAGER).distinct()

        return queryset

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.ProjectCreateSerializer

        return super(ProjectViewSet, self).get_serializer_class()


class ProjectGroupViewSet(viewsets.ModelViewSet):
    queryset = models.ProjectGroup.objects.all()
    serializer_class = serializers.ProjectGroupSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
    # permission_classes = (permissions.IsAuthenticated,)  # TODO: Add permissions for Create/Update


class ProjectGroupMembershipViewSet(rf_mixins.CreateModelMixin,
                                    rf_mixins.RetrieveModelMixin,
                                    rf_mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    rf_viewsets.GenericViewSet):
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
        ]
        order_by = [
            'full_name',
            'native_name',
            'organization',
            'email',
            'phone_number',
            'description',
            'job_title',
        ]


class UserViewSet(viewsets.ModelViewSet):
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


class ProjectPermissionViewSet(rf_mixins.CreateModelMixin,
                               rf_mixins.RetrieveModelMixin,
                               rf_mixins.DestroyModelMixin,
                               mixins.ListModelMixin,
                               rf_viewsets.GenericViewSet):
    queryset = User.groups.through.objects.all()
    serializer_class = serializers.ProjectPermissionSerializer
    filter_backends = (filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def get_queryset(self):
        queryset = super(ProjectPermissionViewSet, self).get_queryset()
        queryset = queryset.exclude(group__projectrole=None)

        # TODO: refactor against django filtering
        user_uuid = self.request.QUERY_PARAMS.get('user', None)
        if user_uuid is not None:
            queryset = queryset.filter(user__uuid=user_uuid)

        return queryset

    def pre_save(self, obj):
        super(ProjectPermissionViewSet, self).pre_save(obj)
        user = self.request.user
        project = obj.group.projectrole.project

        # check for the user role. Inefficient but more readable
        is_manager = project.roles.filter(
            permission_group__user=user, role_type=ProjectRole.MANAGER).exists()
        if is_manager:
            return

        is_customer_owner = project.customer.roles.filter(
            permission_group__user=user, role_type=CustomerRole.OWNER).exists()
        if is_customer_owner:
            return

        raise PermissionDenied()


class CustomerPermissionViewSet(rf_mixins.CreateModelMixin,
                                rf_mixins.RetrieveModelMixin,
                                rf_mixins.DestroyModelMixin,
                                mixins.ListModelMixin,
                                rf_viewsets.GenericViewSet):
    model = User.groups.through
    serializer_class = serializers.CustomerPermissionSerializer
    filter_backends = ()
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def get_queryset(self):
        queryset = super(CustomerPermissionViewSet, self).get_queryset()
        # TODO: Test for it!
        # Only take groups defining customer roles
        queryset = queryset.exclude(group__customerrole=None)

        # TODO: Test for it!
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                group__customerrole__customer__roles__permission_group__user=self.request.user,
                group__customerrole__customer__roles__role_type=models.CustomerRole.OWNER,
            ).distinct()

        return queryset


# XXX: This should be put to models
filters.set_permissions_for_model(
    User.groups.through,
    customer_path='group__projectrole__project__customer',
    project_path='group__projectrole__project',
)
