from mock import patch, Mock

from django.core.management import call_command, CommandError
from django.test import TestCase

from nodeconductor.billing.tasks import create_invoices
from nodeconductor.iaas.tests.factories import CloudProjectMembershipFactory
from nodeconductor.structure.tests.factories import CustomerFactory, ProjectFactory


class CreateInvoicesCommandTest(TestCase):
    def setUp(self):
        self.customer = CustomerFactory()

    def test_create_invoices_command_fail_with_invalid_month(self):
        with self.assertRaisesMessage(CommandError, 'Year and month should be valid values.'):
            call_command('createinvoices', '2015', '22')

    def test_create_invoices_command_fail_with_invalid_year(self):
        with self.assertRaisesMessage(CommandError, 'Year and month should be valid values.'):
            call_command('createinvoices', '2015abc', '03')

    def test_create_invoices_command_fail_with_more_than_three_arguments(self):
        with self.assertRaisesMessage(CommandError, 'Only three arguments can be provided.'):
            call_command('createinvoices', str(self.customer.uuid), '2015', '12', 'invalid')

    def test_create_invoices_command_succeeds_without_arguments(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices')
            self.assertTrue(mocked_task.called)

    def test_create_invoices_command_succeeds_with_one_valid_argument(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices', str(self.customer.uuid))
            self.assertTrue(mocked_task.called)

    def test_create_invoices_command_succeeds_with_two_valid_arguments(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices', '2015', '12')
            self.assertTrue(mocked_task.called)

    def test_create_invoices_command_succeeds_with_three_valid_arguments(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices', str(self.customer.uuid), '2015', '12')
            self.assertTrue(mocked_task.called)


@patch('nodeconductor.iaas.backend.openstack.OpenStackBackend')
@patch('nodeconductor.structure.models.BillingBackend')
class CreateInvoicesTaskTest(TestCase):
    def setUp(self):
        self.customer = CustomerFactory()

        project = ProjectFactory(customer=self.customer)
        self.cpm = CloudProjectMembershipFactory(project=project)

        self.nc_settings = {
            'BILLING': {
                'openstack': {
                    'invoice_meters': {
                        'cpu': ('CPU', 'cpu_hours', 'get_ceilometer_cpu_time', 'hours'),
                        'memory': ('Memory', 'ram_gb', 'get_ceilometer_ram_size', 'GB'),
                    }
                }
            }
        }

    def test_create_invoices_with_invalid_customer_uuid_raises_exception(self, mocked_billing, mocked_openstack):
        with patch('nodeconductor.billing.tasks.logger') as mocked_logger:
            invalid_uuid = 'abc123'
            create_invoices(invalid_uuid, '2015-03-01', '2015-03-31')

            mocked_logger.exception.assert_called_with('Customer with uuid %s does not exist.', invalid_uuid)
            self.assertFalse(mocked_openstack.called)
            self.assertFalse(mocked_billing.called)

    def test_create_invoices_with_valid_uuid_succeeds(self, mocked_billing, mocked_openstack):
        mocked_openstack().get_ceilometer_statistics = Mock(return_value=[Mock()])
        mocked_billing.api.create_invoice = Mock()

        with self.settings(NODECONDUCTOR=self.nc_settings):
            create_invoices(str(self.customer.uuid.hex), '2015-03-01', '2015-03-31')

            self.assertTrue(mocked_openstack().get_ceilometer_statistics.called)
            self.assertTrue(mocked_billing().api.create_invoice.called)
