
from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from nodeconductor.core import models as core_models


@python_2_unicode_compatible
class Invoice(core_models.UuidMixin):

    class Permissions(object):
        customer_path = 'customer'

    customer = models.ForeignKey('structure.Customer', related_name='invoices')
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    date = models.DateField()
    pdf = models.FileField(upload_to='invoices', blank=True, null=True)

    backend_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return "%s %.2f %s" % (self.date, self.amount, self.customer.name)
