from __future__ import unicode_literals

import permission

from django.conf import settings
from django.conf.urls import patterns
from django.conf.urls import include
from django.conf.urls import url
from django.contrib import admin
from django.views.generic import TemplateView

from nodeconductor.core import NodeConductorExtension
from nodeconductor.core.routers import SortedDefaultRouter as DefaultRouter
from nodeconductor.cost_tracking import urls as cost_tracking_urls
from nodeconductor.backup import urls as backup_urls
from nodeconductor.iaas import urls as iaas_urls
from nodeconductor.logging import urls as logging_urls
from nodeconductor.monitoring import urls as monitoring_urls
from nodeconductor.openstack import urls as openstack_urls
from nodeconductor.quotas import urls as quotas_urls
from nodeconductor.structure import urls as structure_urls
from nodeconductor.template import urls as template_urls


admin.autodiscover()
permission.autodiscover()

router = DefaultRouter()
backup_urls.register_in(router)
cost_tracking_urls.register_in(router)
iaas_urls.register_in(router)
logging_urls.register_in(router)
monitoring_urls.register_in(router)
openstack_urls.register_in(router)
quotas_urls.register_in(router)
structure_urls.register_in(router)
template_urls.register_in(router)


urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls), name='admin'),
    url(r'^admintools/', include('admin_tools.urls')),
)

if settings.NODECONDUCTOR.get('EXTENSIONS_AUTOREGISTER'):
    for ext in NodeConductorExtension.get_extensions():
        if ext.django_app() in settings.INSTALLED_APPS:
            urlpatterns += ext.django_urls()
            ext.rest_urls()(router)

urlpatterns += patterns(
    '',
    url(r'^api/', include(router.urls)),
    url(r'^api/', include('nodeconductor.logging.urls')),
    url(r'^api/', include('nodeconductor.iaas.urls')),
    url(r'^api/', include('nodeconductor.structure.urls')),
    url(r'^api/version/', 'nodeconductor.core.views.version_detail'),
    url(r'^api-auth/password/', 'nodeconductor.core.views.obtain_auth_token', name='auth-password'),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url(r'^$', TemplateView.as_view(template_name='landing/index.html')),
)


if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
