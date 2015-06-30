from mock import patch, Mock

from datetime import datetime

from django.core.management import call_command, CommandError
from django.test import TestCase

from nodeconductor.billing.tasks import create_invoices
from nodeconductor.core.utils import datetime_to_timestamp
from nodeconductor.iaas.tests.factories import CloudProjectMembershipFactory
from nodeconductor.structure.tests.factories import CustomerFactory, ProjectFactory


class CreateInvoicesCommandTest(TestCase):
    def setUp(self):
        self.customer = CustomerFactory(billing_backend_id='billing_backend_id')

    def test_create_invoices_command_fail_with_invalid_month(self):
        with self.assertRaisesMessage(CommandError, 'Year and month should be valid values.'):
            call_command('createinvoices', '2015', '22')

    def test_create_invoices_command_fail_with_invalid_year(self):
        with self.assertRaisesMessage(CommandError, 'Year and month should be valid values.'):
            call_command('createinvoices', '2015abc', '03')

    def test_create_invoices_command_fail_with_more_than_three_arguments(self):
        with self.assertRaisesMessage(CommandError, 'Only two or zero arguments can be provided.'):
            call_command('createinvoices', '2015', '12', 'invalid')

    def test_create_invoices_command_fail_with_customer_without_billing_backend(self):
        self.customer.billing_backend_id = ''
        self.customer.save()
        with self.assertRaisesMessage(CommandError, 'Selected customer does not have billing backend id'):
            call_command('createinvoices', customer_uuid=self.customer.uuid.hex)

    def test_create_invoices_command_succeeds_without_arguments(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices')
            self.assertTrue(mocked_task.called)

    def test_create_invoices_command_succeeds_with_one_valid_argument(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices', customer_uuid=self.customer.uuid.hex)
            self.assertTrue(mocked_task.called)

    def test_create_invoices_command_succeeds_with_two_valid_arguments(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices', '2015', '12')
            self.assertTrue(mocked_task.called)

    def test_create_invoices_command_succeeds_with_three_valid_arguments(self):
        with patch('nodeconductor.billing.tasks.create_invoices.delay') as mocked_task:
            call_command('createinvoices', '2015', '12', customer_uuid=self.customer.uuid.hex)
            mocked_task.assert_called_once()


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
                        'cpu': ('CPU', 'cpu_hours', 'hours'),
                        'memory': ('Memory', 'ram_gb', 'GB'),
                    }
                }
            }
        }

    def test_create_invoices_with_invalid_customer_uuid_raises_exception(self, mocked_billing, mocked_openstack):
        with patch('nodeconductor.billing.tasks.logger') as mocked_logger:
            invalid_uuid = 'abc123'
            start_date = datetime(day=1, month=3, year=2015)
            end_date = datetime(day=31, month=3, year=2015)
            create_invoices(invalid_uuid, start_date, end_date)

            mocked_logger.exception.assert_called_with('Customer with uuid %s does not exist.', invalid_uuid)
            self.assertFalse(mocked_openstack.called)
            self.assertFalse(mocked_billing.called)

    @patch('nodeconductor.billing.tasks.generate_usage_pdf')
    def test_create_invoices_with_valid_uuid_succeeds(self, mocked_pdf_generator, mocked_billing, mocked_openstack):
        mocked_openstack().get_nova_usage = Mock(return_value={
            'disk': 1.0,
            'memory': 1.0,
            'cpu': 1.0,
            'servers': 1.0}
        )
        mocked_billing.api.create_invoice = Mock()

        start_date = datetime(day=1, month=3, year=2015)
        end_date = datetime(day=31, month=3, year=2015)

        with self.settings(NODECONDUCTOR=self.nc_settings):
            create_invoices(str(self.customer.uuid.hex), datetime_to_timestamp(start_date),
                            datetime_to_timestamp(end_date))

            self.assertTrue(mocked_openstack().get_nova_usage.called)
            self.assertTrue(mocked_billing().api.create_invoice.called)
            self.assertTrue(mocked_pdf_generator.called)


class CreateSampleDateTest(TestCase):
    def setUp(self):
        self.customer = CustomerFactory()

    def test_create_sample_billing_data_fails(self):
        call_command('createsamplebillingdata')
