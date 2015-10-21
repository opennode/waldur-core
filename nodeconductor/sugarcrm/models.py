from django.db import models

from nodeconductor.structure import models as structure_models


class SugarCRMService(structure_models.Service):
    projects = models.ManyToManyField(
        structure_models.Project, related_name='sugarcrm_services', through='SugarCRMServiceProjectLink')


class SugarCRMServiceProjectLink(structure_models.ServiceProjectLink):
    service = models.ForeignKey(SugarCRMService)

    class Meta:
        unique_together = ('service', 'project')


class CRM(structure_models.Resource):
    service_project_link = models.ForeignKey(
        SugarCRMServiceProjectLink, related_name='crms', on_delete=models.PROTECT)

    @classmethod
    def get_url_name(cls):
        return 'sugarcrm-crms'
