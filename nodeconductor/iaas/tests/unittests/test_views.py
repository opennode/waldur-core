from django.test import TestCase

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.iaas.tests import factories
from nodeconductor.iaas import views
from nodeconductor.cloud.tests import factories as cloud_factories


class InstanceViewSetTest(TestCase):

    def setUp(self):
        self.view = views.InstanceViewSet()

    def test_get_serializer_context(self):
        user = structure_factories.UserFactory()
        mocked_request = type(str('MockedRequest'), (object,), {'user': user})
        self.view.request = mocked_request
        self.view.format_kwarg = None
        self.assertEqual(user, self.view.get_serializer_context()['user'])


class LicenseViewSetTest(TestCase):

    def setUp(self):
        self.view = views.LicenseViewSet()

    def test_get_queryset(self):
        # project and customer
        customer = structure_factories.CustomerFactory()
        project = structure_factories.ProjectFactory(customer=customer)
        # cloud and template
        cloud = cloud_factories.CloudFactory()
        cloud.projects.add(project)
        template = factories.TemplateFactory()
        factories.ImageFactory(cloud=cloud, template=template)
        # license
        license = factories.LicenseFactory()
        license.templates.add(template)
        other_license = factories.LicenseFactory()
        other_customer = structure_factories.CustomerFactory()

        user = structure_factories.UserFactory(is_staff=True, is_superuser=True)
        mocked_request = type(str('MockedRequest'), (object,), {'user': user, 'QUERY_PARAMS': {}})
        self.view.request = mocked_request
        # with no filter
        queryset = self.view.get_queryset()
        self.assertSequenceEqual(list(queryset), [license, other_license])
        # filter by customer uuid
        mocked_request.QUERY_PARAMS = {'customer': str(customer.uuid)}
        self.view.request = mocked_request
        queryset = self.view.get_queryset()
        self.assertSequenceEqual(list(queryset), [license])
        # filter by other customer uuid
        mocked_request.QUERY_PARAMS = {'customer': str(other_customer.uuid)}
        self.view.request = mocked_request
        queryset = self.view.get_queryset()
        self.assertSequenceEqual(list(queryset), [])
