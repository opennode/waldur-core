from django.conf.urls import patterns
from django.conf.urls import url

from nodeconductor.base.views import IndexView

urlpatterns = patterns(
    '',
    url(r'^$', IndexView.as_view(), name='base-index'),
)
