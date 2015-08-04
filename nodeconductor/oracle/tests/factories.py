import factory

from django.core.urlresolvers import reverse

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.oracle import models


class OracleServiceFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OracleService

    name = factory.Sequence(lambda n: 'service%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)
    customer = factory.SubFactory(structure_factories.CustomerFactory)

    @classmethod
    def get_url(self, service=None):
        if service is None:
            service = OracleServiceFactory()
        return 'http://testserver' + reverse('oracle-detail', kwargs={'uuid': service.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('oracle-list')


class OracleServiceProjectLinkFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.OracleServiceProjectLink

    service = factory.SubFactory(OracleServiceFactory)
    project = factory.SubFactory(structure_factories.ProjectFactory)


class TemplateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Template

    name = factory.Sequence(lambda n: 'template%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)
    backend_id = factory.Sequence(lambda n: 'template-id%s' % n)


class ZoneFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Zone

    name = factory.Sequence(lambda n: 'zone%s' % n)
    settings = factory.SubFactory(structure_factories.ServiceSettingsFactory)
    backend_id = factory.Sequence(lambda n: 'zone-id%s' % n)


class DatabaseFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Database

    service_project_link = factory.SubFactory(OracleServiceProjectLinkFactory)
    backend_database_sid = factory.Sequence(lambda n: 'database_sid%s' % n)
    backend_service_name = factory.Sequence(lambda n: 'service_name%s' % n)

    @classmethod
    def get_url(self, database=None):
        if database is None:
            database = DatabaseFactory()
        return 'http://testserver' + reverse('oracle-database-detail', kwargs={'uuid': database.uuid})
