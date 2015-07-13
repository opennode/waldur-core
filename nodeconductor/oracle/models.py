
from django.db import models
from django.core.validators import RegexValidator

from nodeconductor.structure import models as structure_models


class Service(structure_models.Service):
    projects = models.ManyToManyField(
        structure_models.Project, related_name='+', through='ServiceProjectLink')


class ServiceProjectLink(structure_models.ServiceProjectLink):
    service = models.ForeignKey(Service)


class Zone(structure_models.ServiceProperty):
    pass


class Template(structure_models.ServiceProperty):

    class Types:
        DB = 1
        SCHEMA = 2

        CHOICES = (
            (DB, 'Database Platform Template'),
            (SCHEMA, 'Schema Platform Template'),
        )

    type = models.SmallIntegerField(choices=Types.CHOICES)


class Database(structure_models.Resource):
    service_project_link = models.ForeignKey(
        ServiceProjectLink, related_name='databases', on_delete=models.PROTECT)

    backend_database_sid = models.CharField(
        max_length=8,
        blank=True,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9_]{1,8}$',
                message='database_sid must be less than 8 chars and contain only latin letters and digits',
                code='invalid_database_sid',
            )
        ])

    backend_service_name = models.CharField(
        max_length=28,
        blank=True,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9_]{1,28}$',
                message='service_name must be less than 28 chars and contain only latin letters and digits',
                code='invalid_service_name',
            )
        ])
