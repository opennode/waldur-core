
import factory

from mock import patch
from mock_django import mock_signal_receiver
from django.core.urlresolvers import reverse
from rest_framework import test, status

from nodeconductor.iaas.models import OpenStackSettings
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tests.helpers import override_nodeconductor_settings
from nodeconductor.structure import SupportedServices, signals
from nodeconductor.structure.models import Customer, CustomerRole
from nodeconductor.structure.tests import factories


class SuspendServiceTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.customer = factories.CustomerFactory(balance=-10)
        self.customer.add_user(self.user, CustomerRole.OWNER)

    def _get_url(self, view_name, **kwargs):
        return 'http://testserver' + reverse(view_name, kwargs=kwargs)

    def test_debit_customer(self):
        amount = 9.99
        customer = factories.CustomerFactory()

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            with mock_signal_receiver(signals.customer_account_debited) as receiver:
                customer.debit_account(amount)

                receiver.assert_called_once_with(
                    instance=customer,
                    amount=amount,
                    sender=Customer,
                    signal=signals.customer_account_debited,
                )

                mocked_task.assert_called_once_with(
                    'nodeconductor.structure.stop_customer_resources',
                    (customer.uuid.hex,), {}, countdown=2)

                self.assertEqual(customer.balance, -1 * amount)

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

                    response = self.client.post(resource_url + 'start/')
                    self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
