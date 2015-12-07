from django.db.models import Q
import django_filters
import taggit

from nodeconductor.core import filters as core_filters
from nodeconductor.structure import models as structure_models
from nodeconductor.template import models


class ProjectFilter(core_filters.URLFilter):
    """ Filter template groups by project where it can be provisioned.

        Template group can be provisioned in a particular project, if services settings
        of the first template (aka head) are connected to that project.

        If a head template does not have service settings specified, the
        template group is considered to be OK for provisioning in any project.
    """

    def get_project(self, value):
        uuid = self.get_uuid(value)
        try:
            return structure_models.Project.objects.get(uuid=uuid)
        except structure_models.Project.DoesNotExist:
            pass

    def filter(self, qs, value):
        project = self.get_project(value)
        if project is not None:
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
        return qs


class TemplateGroupFilter(django_filters.FilterSet):
    tag = django_filters.ModelMultipleChoiceFilter(
        name='tags__name',
        to_field_name='name',
        lookup_type='in',
        queryset=taggit.models.Tag.objects.all(),
        conjoined=True,
    )
    project = ProjectFilter(view_name='project-detail')

    class Meta(object):
        model = models.TemplateGroup
        fields = ['tag', 'project']
