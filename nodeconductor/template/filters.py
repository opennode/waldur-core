from django.db.models import Q
import django_filters
import taggit

from nodeconductor.core import filters as core_filters
from nodeconductor.structure import models as structure_models
from nodeconductor.template import models


class AbstractProjectFilter(django_filters.Filter):
    """ Filter template groups by project where it can be provisioned.

        Template group can be provisioned in a particular project, if services settings
        of the first template (aka head) are connected to that project.

        If a head template does not have service settings specified, the
        template group is considered to be OK for provisioning in any project.
    """

    def get_project(self, value):
        """ Return Project model instance based on input value """
        raise NotImplementedError

    def filter(self, qs, value):
        if not value:
            return qs
        project = self.get_project(value)
        # for consistency with other filters - return empty list if filtered project does not exists
        if project is None:
            return qs.none()

        project_head_templates = (
            models.Template.objects
            .filter(order_number=1)
            .filter(
                Q(service_settings__isnull=True) |
                Q(service_settings__shared=True) |
                Q(service_settings__customer__projects=project)
            )
        )
        return qs.filter(templates=project_head_templates)


class URLProjectFilter(AbstractProjectFilter, core_filters.URLFilter):

    def get_project(self, value):
        uuid = self.get_uuid(value)
        try:
            return structure_models.Project.objects.get(uuid=uuid)
        except structure_models.Project.DoesNotExist:
            return


class UUIDProjectFilter(AbstractProjectFilter):

    def get_project(self, value):
        try:
            return structure_models.Project.objects.get(uuid=value)
        except structure_models.Project.DoesNotExist:
            return


class TemplateGroupFilter(django_filters.FilterSet):
    tag = django_filters.ModelMultipleChoiceFilter(
        name='tags__name',
        to_field_name='name',
        lookup_type='in',
        queryset=taggit.models.Tag.objects.all(),
    )
    rtag = django_filters.ModelMultipleChoiceFilter(
        name='tags__name',
        to_field_name='name',
        queryset=taggit.models.Tag.objects.all(),
        conjoined=True,
    )
    templates_tag = django_filters.ModelMultipleChoiceFilter(
        name='templates__tags__name',
        to_field_name='name',
        lookup_type='in',
        queryset=taggit.models.Tag.objects.all(),
    )
    templates_rtag = django_filters.ModelMultipleChoiceFilter(
        name='templates__tags__name',
        to_field_name='name',
        queryset=taggit.models.Tag.objects.all(),
        conjoined=True,
    )
    project = URLProjectFilter(view_name='project-detail')
    project_uuid = UUIDProjectFilter()
    name = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = models.TemplateGroup
        fields = ['tag', 'rtag', 'templates_tag', 'templates_rtag', 'name', 'project', 'project_uuid']
        order_by = ['name', '-name']
