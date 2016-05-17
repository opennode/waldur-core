import factory

from mock_django import mock_signal_receiver
from django.core.urlresolvers import reverse
from rest_framework import test, status

from nodeconductor.iaas.models import OpenStackSettings
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tests.helpers import override_nodeconductor_settings
from nodeconductor.structure import SupportedServices, signals
from nodeconductor.structure.models import Customer, CustomerRole, VirtualMachineMixin, ProjectRole
from nodeconductor.structure.tests import factories


class SuspendServiceTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.customer = factories.CustomerFactory(balance=-10)
        self.customer.add_user(self.user, CustomerRole.OWNER)

    def _get_url(self, view_name, **kwargs):
        return 'http://testserver' + reverse(view_name, kwargs=kwargs)

    def test_credit_customer(self):
        amount = 7.45
        customer = factories.CustomerFactory()

        with mock_signal_receiver(signals.customer_account_credited) as receiver:
            customer.credit_account(amount)

            receiver.assert_called_once_with(
                instance=customer,
                amount=amount,
                sender=Customer,
                signal=signals.customer_account_credited,
            )

            self.assertEqual(customer.balance, amount)

    # XXX: This test is too complex and tries to cover too many applications in one. It has to be  rewritten.
    # Possible solutions:
    #  1. Make this text abstract and override it in other applications.
    #  2. Register factories and other test related stuff for each application and use them in this test.
    @override_nodeconductor_settings(SUSPEND_UNPAID_CUSTOMERS=True)
    def test_modify_suspended_services_and_resources(self):
        self.client.force_authenticate(user=self.user)

        for service_type, models in SupportedServices.get_service_models().items():
            # XXX: quick fix for iaas cloud. Can be removed after iaas application refactoring.
            if service_type == -1:
                continue
            settings = factories.ServiceSettingsFactory(
                customer=self.customer, type=service_type, shared=True)

            class ServiceFactory(factory.DjangoModelFactory):
                class Meta(object):
                    model = models['service']

            class ServiceProjectLinkFactory(factory.DjangoModelFactory):
                class Meta(object):
                    model = models['service_project_link']

            if service_type == SupportedServices.Types.IaaS:
                service = ServiceFactory(customer=self.customer, state=SynchronizationStates.IN_SYNC)
                OpenStackSettings.objects.get_or_create(
                    auth_url='http://example.com:5000/v2',
                    defaults={
                        'username': 'admin',
                        'password': 'password',
                        'tenant_name': 'admin',
                    })

            else:
                service = models['service'].objects.create(
                    customer=self.customer, settings=settings, name=settings.name, available_for_all=True)

            service_url = self._get_url(
                SupportedServices.get_detail_view_for_model(models['service']), uuid=service.uuid.hex)

            response = self.client.patch(service_url, {'name': 'new name'})
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            response = self.client.delete(service_url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            for resource_model in models['resources']:
                if service_type == SupportedServices.Types.IaaS:
                    continue

                class ResourceFactory(factory.DjangoModelFactory):
                    class Meta(object):
                        model = resource_model

                project = factories.ProjectFactory(customer=self.customer)
                spl = models['service_project_link'].objects.get(service=service, project=project)

                # XXX: Some resources can have more required fields and creation will fail. Lets just skip them.
                try:
                    resource = ResourceFactory(service_project_link=spl)
                except:
                    pass
                else:
                    resource_url = self._get_url(
                        SupportedServices.get_detail_view_for_model(resource_model), uuid=resource.uuid.hex)

                    if isinstance(resource, VirtualMachineMixin):
                        response = self.client.post(resource_url + 'start/')
                        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class ServiceResourcesCounterTest(test.APITransactionTestCase):
    """
    There's one shared service. Also there are 2 users each of which has one project.
    There's one VM in each project. Service counters for each user should equal 1.
    For staff user resource counter should equal 2.
    """
    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.settings = factories.ServiceSettingsFactory(shared=True)
        self.service = factories.TestServiceFactory(customer=self.customer, settings=self.settings)

        self.user1 = factories.UserFactory()
        self.project1 = factories.ProjectFactory(customer=self.customer)
        self.project1.add_user(self.user1, ProjectRole.ADMINISTRATOR)
        self.spl1 = factories.TestServiceProjectLinkFactory(service=self.service, project=self.project1)
        self.vm1 = factories.TestInstanceFactory(service_project_link=self.spl1)

        self.user2 = factories.UserFactory()
        self.project2 = factories.ProjectFactory(customer=self.customer)
        self.project2.add_user(self.user2, ProjectRole.ADMINISTRATOR)
        self.spl2 = factories.TestServiceProjectLinkFactory(service=self.service, project=self.project2)
        self.vm2 = factories.TestInstanceFactory(service_project_link=self.spl2)

        self.service_url = factories.TestServiceFactory.get_url(self.service)

    def test_counters_for_shared_providers_should_be_filtered_by_user(self):
        self.client.force_authenticate(self.user1)
        response = self.client.get(self.service_url)
        self.assertEqual(1, response.data['resources_count'])

        self.client.force_authenticate(self.user2)
        response = self.client.get(self.service_url)
        self.assertEqual(1, response.data['resources_count'])

    def test_counters_are_not_filtered_for_staff(self):
        self.client.force_authenticate(factories.UserFactory(is_staff=True))
        response = self.client.get(self.service_url)
        self.assertEqual(2, response.data['resources_count'])
