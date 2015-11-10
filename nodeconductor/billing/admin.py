from django.contrib import admin, messages
from django.conf.urls import patterns, url
from django.core.urlresolvers import reverse
from django.shortcuts import redirect

from nodeconductor.billing import models
from nodeconductor.billing.backend import BillingBackend
from nodeconductor.billing.models import PaidResource
from nodeconductor.billing.tasks import update_today_usage_of_resource


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date', 'amount',)

    def get_urls(self):
        my_urls = patterns(
            '',
            url(r'^move_date/$', self.admin_site.admin_view(self.move_date)),
        )
        return my_urls + super(InvoiceAdmin, self).get_urls()

    def move_date(self, request):
        for model in PaidResource.get_all_models():
            for resource in model.objects.all():
                try:
                    update_today_usage_of_resource(resource.to_string())
                except Exception as e:
                    self.message_user(
                        request,
                        "Can't post usage for %s: %s" % (resource, e),
                        level=messages.ERROR)

        backend = BillingBackend()
        backend.api.test.move_days(31)

        self.message_user(request, "KillBill invoices generated. Now please choose customers to sync.")
        return redirect(reverse('admin:structure_customer_changelist'))


admin.site.register(models.Invoice, InvoiceAdmin)
