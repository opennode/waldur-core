from admin_tools.menu import items, Menu
from django.urls import reverse
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
        'nodeconductor_assembly_waldur.packages.*',
        'nodeconductor_azure.*',
        'nodeconductor_openstack.*',
        'nodeconductor_aws.*',
        'nodeconductor_digitalocean.*',
        'nodeconductor_ldap.*',
    )

    USERS = (
        'nodeconductor.core.models.User',
        'nodeconductor.core.models.SSHPublicKey',
        'nodeconductor.users.models.Invitation',
    )

    ACCOUNTING = (
        'nodeconductor_assembly_waldur.invoices.*',
        'nodeconductor.cost_tracking.*',
    )

    APPLICATION_PROVIDERS = (
        'nodeconductor_sugarcrm.*',
        'nodeconductor_saltstack.*',
        'nodeconductor_zabbix.*',
        'nodeconductor_jira.*',
        'nodeconductor_gitlab.*',
        'nodeconductor_oracle_dbaas.*',
        'nodeconductor_paas_oracle.*',
        'waldur_ansible.*',
    )

    SUPPORT_MODULES = (
        'nodeconductor_assembly_waldur.support.*',
    )

    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)
        self.children += [
            items.MenuItem(_('Dashboard'), reverse('admin:index')),
            items.ModelList(
                _('Users'),
                models=self.USERS
            ),
            items.ModelList(
                _('Structure'),
                models=(
                    'nodeconductor.structure.*',
                )
            ),
            CustomAppList(
                _('Accounting'),
                models=self.ACCOUNTING,
            ),

            CustomAppList(
                _('Providers'),
                models=self.IAAS_CLOUDS,
            ),
            CustomAppList(
                _('Applications'),
                models=self.APPLICATION_PROVIDERS,
            ),
            CustomAppList(
                _('Support'),
                models=self.SUPPORT_MODULES,
            ),
            CustomAppList(
                _('Utilities'),
                exclude=('django.core.*',
                         'django_openid_auth.*',
                         'rest_framework.authtoken.*',
                         'nodeconductor.core.*',
                         'nodeconductor.structure.*',
                         )
                        + self.IAAS_CLOUDS
                        + self.APPLICATION_PROVIDERS
                        + self.SUPPORT_MODULES
                        + self.ACCOUNTING
                        + self.USERS
            ),

        ]
