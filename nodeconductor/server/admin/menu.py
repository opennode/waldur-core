from admin_tools.menu import items, Menu
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _


class CustomMenu(Menu):
    """
    Custom Menu for admin site.
    """
    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)
        self.children += [
            items.MenuItem(_('Dashboard'), reverse('admin:index')),
            items.Bookmarks(),
            items.AppList(
                _('Applications'),
                exclude=('django.core.*',
                         'rest_framework.authtoken.*',
                         'nodeconductor.core.*',
                         )
            ),
            items.ModelList(
                _('User management'),
                models=('nodeconductor.core.*',)
            ),
        ]
