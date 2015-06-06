from django.contrib import admin

from nodeconductor.billing import models


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date', 'amount',)


class PricelistAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'backend_id')


admin.site.register(models.Invoice, InvoiceAdmin)
admin.site.register(models.PriceList, PricelistAdmin)
