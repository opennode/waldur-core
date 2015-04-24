from django.conf.urls import patterns

from nodeconductor.jira import views


def register_in(router):
    router.register(r'issues', views.IssueViewSet, base_name='issue')


urlpatterns = patterns(
    '',
)
