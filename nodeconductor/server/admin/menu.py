from admin_tools.menu import items, Menu
from django.core.urlresolvers import reverse
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy as _


class CustomAppList(items.AppList):
    def init_with_context(self, context):
        context_items = self._visible_models(context['request'])
        apps = {}
        for model, perms in context_items:
            if not perms['change']:
                continue
            app_label = model._meta.app_label
            if app_label not in apps:
                apps[app_label] = {
                    'title': capfirst(model._meta.app_config.verbose_name),
                    'url': self._get_admin_app_list_url(model, context),
                    'models': []
                }
            apps[app_label]['models'].append({
                'title': capfirst(model._meta.verbose_name_plural),
                'url': self._get_admin_change_url(model, context)
            })

        for app in sorted(apps, key=lambda k: apps[k]['title']):
            app_dict = apps[app]
            item = items.MenuItem(title=app_dict['title'], url=app_dict['url'])
            # sort model list alphabetically
            apps[app]['models'].sort(key=lambda x: x['title'])
            for model_dict in apps[app]['models']:
                item.children.append(items.MenuItem(**model_dict))
            self.children.append(item)


class CustomMenu(Menu):
    """
    Custom Menu for admin site.
    """

    IAAS_CLOUDS = (
        'nodeconductor_plus.azure.*',
        'nodeconductor_plus.aws.*',
        'nodeconductor_plus.digitalocean.*',
        'nodeconductor.openstack.*'
    )

    APPLICATION_PROVIDERS = (
        'nodeconductor_sugarcrm.*',
        'nodeconductor_saltstack.*',
        'nodeconductor_zabbix.*',
        'nodeconductor_plus.gitlab.*',
        'nodeconductor_oracle_dbaas.*'
    )

    SUPPORT_MODULES = (
        'nodeconductor_plus.plans.*',
        'nodeconductor_plus.premium_support.*',
    )

    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)
        self.children += [
            items.MenuItem(_('Dashboard'), reverse('admin:index')),
            CustomAppList(
                _('Core'),
                exclude=('django.core.*',
                         'rest_framework.authtoken.*',
                         'nodeconductor.core.*',
                         'nodeconductor.structure.*',
                         ) + self.IAAS_CLOUDS + self.APPLICATION_PROVIDERS + self.SUPPORT_MODULES
            ),
            items.ModelList(
                _('Structure'),
                models=('nodeconductor.core.*',
                        'nodeconductor_organization.*',
                        'nodeconductor.structure.*',
                )
            ),
            CustomAppList(
                _('IaaS clouds'),
                models=self.IAAS_CLOUDS,
            ),
            CustomAppList(
                _('Applications'),
                models=self.APPLICATION_PROVIDERS,
            ),
            CustomAppList(
                _('Subscriptions and support'),
                models=self.SUPPORT_MODULES,
            ),


        ]
