
from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from nodeconductor.core import models as core_models
from nodeconductor.logging.log import LoggableMixin


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
