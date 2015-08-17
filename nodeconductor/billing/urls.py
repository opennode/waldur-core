from django.conf.urls import patterns, url

from nodeconductor.billing import views


def register_in(router):
    router.register(r'invoices', views.InvoiceViewSet)
    router.register(r'payments', views.PaymentView, base_name='payment')


urlpatterns = patterns(
    '',
    url(r'^orders/$', views.OrdersView.as_view(), name='order'),
)
