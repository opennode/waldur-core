from django.conf.urls import patterns
from django.conf.urls import url

from nodeconductor.vm.views import VmList

urlpatterns = patterns(
    '',
    url(r'^vms/$', VmList.as_view(), name='vm-list'),  # XXX: Should namespaces be used?
)
