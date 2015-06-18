from django.shortcuts import redirect
from django.conf.urls import patterns, url
from django.core.urlresolvers import reverse
from django.contrib import admin

from nodeconductor.billing import models
from nodeconductor.core.tasks import send_task


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date', 'amount',)


class PricelistAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'backend_id')

    def get_urls(self):
        urls = super(PricelistAdmin, self).get_urls()
        my_urls = patterns('', url(r'^sync/$', self.admin_site.admin_view(self.sync)))
        return my_urls + urls

    def sync(self, request):
        send_task('billing', 'sync_pricelist')()
        self.message_user(request, "Pricelists scheduled for sync")
        return redirect(reverse('admin:billing_pricelist_changelist'))


admin.site.register(models.Invoice, InvoiceAdmin)
admin.site.register(models.PriceList, PricelistAdmin)
