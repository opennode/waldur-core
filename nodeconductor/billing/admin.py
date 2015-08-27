from django.contrib import admin

from nodeconductor.billing import models


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date', 'amount',)


admin.site.register(models.Invoice, InvoiceAdmin)
