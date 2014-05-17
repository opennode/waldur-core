from django.conf.urls import patterns
from django.conf.urls import url
from django.views.generic import TemplateView

from nodeconductor.base.views import IndexView


urlpatterns = patterns(
    '',
    url(r'^$', TemplateView.as_view(template_name='index.html'), name='index'),
    url(r'^login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}),

)
