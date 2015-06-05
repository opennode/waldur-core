from __future__ import unicode_literals

from django.conf import settings
from django.conf.urls import patterns
from django.conf.urls import include
from django.conf.urls import url
from django.contrib import admin
from django.views.generic import TemplateView
import permission

from nodeconductor.core.routers import SortedDefaultRouter as DefaultRouter
from nodeconductor.backup import urls as backup_urls
from nodeconductor.billing import urls as billing_urls
from nodeconductor.iaas import urls as iaas_urls
from nodeconductor.jira import urls as jira_urls
from nodeconductor.oracle import urls as oracle_urls
from nodeconductor.logging import urls as logging_urls
from nodeconductor.quotas import urls as quotas_urls
from nodeconductor.structure import urls as structure_urls
from nodeconductor.template import urls as template_urls


nc_plus_urls = getattr(settings, 'NODECONDUCTOR_PLUS_URLS', ())
register_nc_plus = settings.NODECONDUCTOR_PLUS_URLS_AUTOREGISTER and nc_plus_urls

admin.autodiscover()
permission.autodiscover()

router = DefaultRouter()
iaas_urls.register_in(router)
oracle_urls.register_in(router)
structure_urls.register_in(router)
template_urls.register_in(router)
billing_urls.register_in(router)
backup_urls.register_in(router)
quotas_urls.register_in(router)
jira_urls.register_in(router)
logging_urls.register_in(router)


urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls), name='admin'),
)

if register_nc_plus:
    for entry_point in nc_plus_urls:
        url_module = entry_point.load()
        if hasattr(url_module, 'register_in'):
            url_module.register_in(router)
        if hasattr(url_module, 'urlpatterns'):
            urlpatterns += url_module.urlpatterns

urlpatterns += patterns(
    '',
    url(r'^api/', include(router.urls)),
    url(r'^api/', include('nodeconductor.logging.urls')),
    url(r'^api/', include('nodeconductor.iaas.urls')),
    url(r'^api/', include('nodeconductor.structure.urls')),
    url(r'^api/version/', 'nodeconductor.core.views.version_detail'),
    url(r'^api-auth/password/', 'nodeconductor.core.views.obtain_auth_token'),
    url(r'^api-auth/saml2/', 'nodeconductor.core.views.assertion_consumer_service'),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url(r'^$', TemplateView.as_view(template_name='landing/index.html')),
)


if settings.DEBUG:
    (r'^%{static_url}/(?P<path>.*)$'.format(static_url=settings.STATIC_URL),
        'django.views.static.serve', {'document_root': settings.STATIC_ROOT}),
