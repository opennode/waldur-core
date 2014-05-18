from django.conf import settings

from django.conf.urls import patterns
from django.conf.urls import include
from django.conf.urls import url
from django.contrib import admin



urlpatterns = patterns(
    '',
    url(r'^', include('nodeconductor.base.urls')),
    url(r'^vm/', include('nodeconductor.vm.urls')),
    url(r'^admin/', include(admin.site.urls), name='admin'),
)

if settings.DEBUG:
    (r'^%{static_url}/(?P<path>.*)$'.format(static_url=settings.STATIC_URL),
        'django.views.static.serve', {'document_root': settings.STATIC_ROOT}),
