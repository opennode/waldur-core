import logging
import functools

from django.db import models
from django_fsm import transition, FSMIntegerField
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.contenttypes.models import ContentType
from model_utils.models import TimeStampedModel

from nodeconductor.core import models as core_models
from nodeconductor.logging.log import LoggableMixin
from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.cost_tracking.models import DefaultPriceListItem


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class PriceList(core_models.UuidMixin, core_models.DescribableMixin):

    # Model doesn't inherit NameMixin, because name field must be unique.
    name = models.CharField(max_length=150, unique=True)
    price = models.DecimalField(max_digits=9, decimal_places=2)
    backend_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return "%s %.2f" % (self.name, self.price)


@python_2_unicode_compatible
class Invoice(LoggableMixin, core_models.UuidMixin):

    class Permissions(object):
        customer_path = 'customer'

    customer = models.ForeignKey('structure.Customer', related_name='invoices')
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    date = models.DateField()
    pdf = models.FileField(upload_to='invoices', blank=True, null=True)
    usage_pdf = models.FileField(upload_to='invoices_usage', blank=True, null=True)

    status = models.CharField(max_length=80, blank=True)

    backend_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return "%s %.2f %s" % (self.date, self.amount, self.customer.name)

    def get_log_fields(self):
        return ('uuid', 'customer', 'amount', 'date', 'status')


class Payment(LoggableMixin, TimeStampedModel, core_models.UuidMixin):

    class Permissions(object):
        customer_path = 'customer'

    class States(object):
        INIT = 0
        CREATED = 1
        APPROVED = 2
        CANCELLED = 3
        ERRED = 4

    STATE_CHOICES = (
        (States.INIT, 'Initial'),
        (States.CREATED, 'Created'),
        (States.APPROVED, 'Approved'),
        (States.ERRED, 'Erred'),
    )

    state = FSMIntegerField(default=States.INIT, choices=STATE_CHOICES)

    customer = models.ForeignKey('structure.Customer')
    amount = models.DecimalField(max_digits=9, decimal_places=2)

    # Payment ID is required and fetched from backend
    backend_id = models.CharField(max_length=255, null=True)

    # URL is fetched from backend
    approval_url = models.URLField()

    def __str__(self):
        return "%s %.2f %s" % (self.modified, self.amount, self.customer.name)

    def get_log_fields(self):
        return ('uuid', 'customer', 'amount', 'modified', 'status')

    @transition(field=state, source=States.INIT, target=States.CREATED)
    def set_created(self):
        pass

    @transition(field=state, source=States.CREATED, target=States.APPROVED)
    def set_approved(self):
        pass

    @transition(field=state, source=States.CREATED, target=States.CANCELLED)
    def set_cancelled(self):
        pass

    @transition(field=state, source='*', target=States.ERRED)
    def set_erred(self):
        pass


class PaidResource(models.Model):
    """ Extend Resource model with methods to track usage cost and handle orders """

    class Meta(object):
        abstract = True

    class Order(object):
        def __init__(self, instance):
            self.instance = instance

        def safe_method(func):
            @functools.wraps(func)
            def wrapped(self, *args, **kwargs):
                try:
                    func(self, *args, **kwargs)
                except BillingBackendError as e:
                    # silently fail with error log record
                    logger.error(
                        "Failed to perform order %s for resource %s: %s",
                        func.__name__, self.instance, e)
            return wrapped

        @property
        def backend(self):
            return self.instance.service_project_link.service.customer.get_billing_backend()

        @safe_method
        def setup(self):
            # Fetch *any* item of specific content type to get backend product id
            resource_content_type = ContentType.objects.get_for_model(self.instance)
            product = DefaultPriceListItem.objects.filter(
                resource_content_type=resource_content_type).first()

            if not product:
                raise BillingBackendError(
                    "Product %s is missing on backend" % resource_content_type)

            if self.instance.billing_backend_id:
                raise BillingBackendError(
                    "Order for resource %s is placed already" % self.instance)

            self.backend.setup_product(self.instance, product.backend_product_id)

        @safe_method
        def confirm(self):
            self.backend.confirm_product_setup(self.instance)

        @safe_method
        def cancel(self):
            self.backend.cancel_product_setup(self.instance)

        @safe_method
        def update(self, **options):
            if not self.instance.billing_backend_purchase_order_id:
                raise BillingBackendError(
                    "Order for resource %s is missing on backend" % self.instance)

            self.backend.update_product(self.instance, **options)

        @safe_method
        def terminate(self):
            if self.instance.billing_backend_id:
                self.backend.terminate_product(self.instance)

        def reset(self):
            self.instance.billing_backend_id = ''
            self.instance.billing_backend_template_id = ''
            self.instance.billing_backend_purchase_order_id = ''
            self.instance.save(update_fields=['billing_backend_id',
                                              'billing_backend_template_id',
                                              'billing_backend_purchase_order_id'])

        def _propagate_default_options(self, options):
            try:
                defaults = self.instance.get_default_price_options()
            except NotImplementedError:
                pass
            else:
                for opt in options:
                    if options[opt] in (None, '') and opt in defaults:
                        options[opt] = defaults[opt]

            return options

    billing_backend_purchase_order_id = models.CharField(
        max_length=255, blank=True, help_text='ID of a purchase order in backend that created a resource')
    billing_backend_id = models.CharField(max_length=255, blank=True, help_text='ID of a resource in backend')
    billing_backend_template_id = models.CharField(max_length=255, blank=True,
                                                   help_text='ID of a template in backend used for creating a resource')

    def get_default_price_options(self):
        raise NotImplementedError

    def get_price_options(self):
        raise NotImplementedError

    def __init__(self, *args, **kwargs):
        super(PaidResource, self).__init__(*args, **kwargs)
        self.order = self.Order(self)
