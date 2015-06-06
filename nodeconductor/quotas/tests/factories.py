from django.core.urlresolvers import reverse
import factory
import factory.fuzzy

# Dependency from `iaas` application exists only in tests
# If `quotas` application will become standalone application,
# then Membership model have to be replaced with dumb test model
from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.quotas import models


class QuotaFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Quota

    scope = factory.SubFactory(iaas_factories.CloudProjectMembershipFactory)
    limit = factory.fuzzy.FuzzyFloat(low=16.0, high=1024.0)
    usage = factory.LazyAttribute(lambda q: q.limit / 2)
    name = factory.Iterator(['vcpu', 'storage', 'max_instances', 'ram'])

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('quota-list')

    @classmethod
    def get_url(self, quota):
        if quota is None:
            quota = QuotaFactory()
        return 'http://testserver' + reverse('quota-detail', kwargs={'uuid': quota.uuid})
