from nodeconductor.support import views


def register_in(router):
    router.register(r'issues', views.IssueViewSet, base_name='issue')
    router.register(r'issues/(?P<pk>[A-Z0-9_-]+)/comments', views.CommentViewSet, base_name='issue-comments')
