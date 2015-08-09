import logging

from django.db import models
from django_fsm import transition, FSMIntegerField
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.contenttypes.models import ContentType
from model_utils.models import TimeStampedModel

from nodeconductor.core import models as core_models
from nodeconductor.logging.log import LoggableMixin
from nodeconductor.billing.backend import BillingBackendError


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

        @property
        def id(self):
            return self.instance.billing_backend_purchase_order_id

        @id.setter
        def id(self, val):
            try:
                self.instance.billing_backend_purchase_order_id = val
                self.instance.save(update_fields=['billing_backend_purchase_order_id'])
            except self.instance.DoesNotExist:
                pass

        @property
        def product_id(self):
            return self.instance.billing_backend_id

        @product_id.setter
        def product_id(self, val):
            try:
                self.instance.billing_backend_id = val
                self.instance.save(update_fields=['billing_backend_id'])
            except self.instance.DoesNotExist:
                pass

        @property
        def template_id(self):
            return self.instance.billing_backend_template_id

        @template_id.setter
        def template_id(self, val):
            try:
                self.instance.billing_backend_template_id = val
                self.instance.save(update_fields=['billing_backend_template_id'])
            except self.instance.DoesNotExist:
                pass

        @property
        def backend(self):
            return self.instance.service_project_link.service.customer.get_billing_backend()

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

        def add(self):
            options = self.instance.get_price_options()
            options = self._propagate_default_options(options)
            resource_content_type = ContentType.objects.get_for_model(self.instance)
            self.id, self.product_id, self.template_id = self.backend.add_order(resource_content_type,
                                                                                self.instance.name,
                                                                                **options)

        def update(self, **options):
            options = self._propagate_default_options(options)
            self.backend.update_order(self.product_id, self.template_id, **options)

        def accept(self):
            self.backend.accept_order(self.id)

        def cancel(self):
            self.backend.cancel_order(self.id)

        def cancel_purchase(self):
            if self.product_id:
                try:
                    self.backend.cancel_purchase(self.product_id)
                except BillingBackendError as e:
                    logger.error('Failed to cancel order with a known ID %s: %s', self.id, e.message)

        def delete(self):
            if self.id:
                self.backend.delete_order(self.id)
                self.id = ''

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
