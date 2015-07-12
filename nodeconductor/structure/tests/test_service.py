
import factory

from mock import patch
from mock_django import mock_signal_receiver
from django.apps import apps
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from rest_framework import test, status

from nodeconductor.iaas.models import OpenStackSettings
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.structure import signals
from nodeconductor.structure.models import Customer, CustomerRole, ServiceSettings
from nodeconductor.structure.tests import factories
from nodeconductor.structure.serializers import SUPPORTED_SERVICES


class SuspendServiceTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.customer = factories.CustomerFactory(balance=-10)
        self.customer.add_user(self.user, CustomerRole.OWNER)

    def _get_url(self, view_name, **kwargs):
        view = view_name.replace('-list', '-detail') if kwargs else view_name
        return 'http://testserver' + reverse(view, kwargs=kwargs)

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
                    (customer.uuid.hex,), {})

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

    @override_settings(NODECONDUCTOR={'SUSPEND_UNPAID_CUSTOMERS': True})
    def test_modify_suspended_services_and_resources(self):
        self.client.force_authenticate(user=self.user)

        for service_model_name, service_attrs in SUPPORTED_SERVICES.items():

            service_model = apps.get_model(service_model_name)
            service_type = None
            for k, v in ServiceSettings.Types.CHOICES:
                if v == service_attrs['name']:
                    service_type = k
            settings = factories.ServiceSettingsFactory(customer=self.customer, type=service_type)

            class ServiceFactory(factory.DjangoModelFactory):
                class Meta(object):
                    model = service_model

            if service_model_name.startswith('iaas'):
                service = ServiceFactory(customer=self.customer, state=SynchronizationStates.IN_SYNC)
                OpenStackSettings.objects.get_or_create(
                    auth_url='http://example.com:5000/v2',
                    defaults={
                        'username': 'admin',
                        'password': 'password',
                        'tenant_name': 'admin',
                    })

            else:
                service = ServiceFactory(customer=self.customer, settings=settings)

            service_url = self._get_url(
                service_attrs['view_name'], uuid=service.uuid.hex)

            response = self.client.patch(service_url, {'name': 'new name'})
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            response = self.client.delete(service_url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            response = self.client.post(
                self._get_url(service_attrs['view_name']), {
                    'name': 'new service',
                    'customer': factories.CustomerFactory.get_url(self.customer),
                    'settings': factories.ServiceSettingsFactory.get_url(settings),
                    'auth_url': 'http://example.com:5000/v2',
                })
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

            for resource_model_name, resource_attrs in service_attrs['resources'].items():

                if resource_model_name.startswith('iaas'):
                    continue

                class ResourceFactory(factory.DjangoModelFactory):
                    class Meta(object):
                        model = apps.get_model(resource_model_name)

                class ServiceProjectLinkFactory(factory.DjangoModelFactory):
                    class Meta(object):
                        model = service_model._meta.get_all_related_objects_with_model()[0][0].model

                spl = ServiceProjectLinkFactory(
                    service=service,
                    project=factories.ProjectFactory(customer=self.customer))
                resource = ResourceFactory(service_project_link=spl)
                resource_url = self._get_url(resource_attrs['view_name'], uuid=resource.uuid.hex)

                response = self.client.post(resource_url + 'start/')
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
