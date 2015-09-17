from __future__ import unicode_literals

from django.db.models import Q
from django.contrib.contenttypes import models as ct_models
import django_filters

from nodeconductor.core import filters as core_filters
from nodeconductor.backup import models, utils
from nodeconductor.structure import filters as structure_filters


class BackupPermissionFilterBackend():

    def _get_user_visible_model_instances_ids(self, user, model):
        queryset = structure_filters.filter_queryset_for_user(model.objects.all(), user)
        return queryset.values_list('pk', flat=True)

    def filter_queryset(self, request, queryset, view):
        """
        Filter backups with source to which user has view access
        """
        q_query = Q()
        for strategy in utils.get_backup_strategies().values():
            model = strategy.get_model()
            model_content_type = ct_models.ContentType.objects.get_for_model(model)
            instances_ids = self._get_user_visible_model_instances_ids(request.user, model)
            q_query |= (Q(content_type=model_content_type) & Q(object_id__in=instances_ids))
        return queryset.filter(q_query)


class BackupProjectFilterBackend(object):
    def filter_queryset(self, request, queryset, view):
        project_uuid = request.query_params.get('project_uuid')

        if not project_uuid:
            return queryset

        query = Q()
        for strategy in utils.get_backup_strategies().values():
            model = strategy.get_model()
            content_type = ct_models.ContentType.objects.get_for_model(model)
            ids = model.objects.filter(project__uuid=project_uuid).values_list('pk', flat=True)
            query |= Q(content_type=content_type, object_id__in=ids)
        return queryset.filter(query)


class BackupSourceFilterBackend(core_filters.GenericKeyFilterBackend):

    def get_field_name(self):
        return 'backup_source'

    def get_related_models(self):
        return utils.get_backupable_models()


class BackupScheduleFilter(django_filters.FilterSet):
    description = django_filters.CharFilter(
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.BackupSchedule
        fields = (
            'description',
        )


class BackupFilter(django_filters.FilterSet):
    description = django_filters.CharFilter(
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.Backup
        fields = (
            'description',
        )
