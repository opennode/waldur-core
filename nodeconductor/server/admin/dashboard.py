from django.utils.translation import ugettext_lazy as _
from fluent_dashboard.dashboard import modules, FluentIndexDashboard, FluentAppIndexDashboard
from fluent_dashboard.modules import AppIconList, PersonalModule

from nodeconductor.core import NodeConductorExtension
from nodeconductor import __version__

class CustomIndexDashboard(FluentIndexDashboard):
    """
    Custom index dashboard for admin site.
    """
    title = 'NodeConductor administration'

    def _get_installed_plugin_info(self):
        result = [
            {
                'title': _('NodeConductor %s' % __version__),
                'url': 'http://nodeconductor.readthedocs.org/en/stable/',
                'external': True,
            },
        ]

        documentation = {
            'nodeconductor_organization': 'http://nodeconductor-organization.readthedocs.org/en/latest/',
            'nodeconductor_saltstack': 'http://nodeconductor-saltstack.readthedocs.org/',
            'nodeconductor_sugarcrm': 'http://nodeconductor-sugarcrm.readthedocs.org/',

        }
        plugins = set()
        for ext in NodeConductorExtension.get_extensions():
            base_name = ext.__module__.split('.')[0]
            module = __import__(base_name)
            name = 'NodeConductor %s' % ' '.join(base_name.split('_')[1:]).title()
            plugins.add((name, getattr(module, '__version__', 'N/A'), module.__doc__))

        for plugin, version, description in sorted(plugins):
            result.append(
                {
                    'title': '%s %s' % (plugin, version),
                    'url': documentation.get(plugin,
                                             'http://nodeconductor.readthedocs.org/en/latest/#nodeconductor-plugins'),
                    'description': description,
                    'external': True
                }
            )

        return result

    def __init__(self, **kwargs):
        FluentIndexDashboard.__init__(self, **kwargs)
        self.children.append(modules.Group(
            title="IaaS",
            display="tabs",
            children=[
                modules.ModelList(
                    title='Virtual Machine',
                    models=('nodeconductor.iaas.models.Instance',
                            'nodeconductor.iaas.models.InstanceSlaHistory',
                            'nodeconductor.iaas.models.Template',
                            'nodeconductor.iaas.models.TemplateLicense',
                            )
                ),
                modules.ModelList(
                    title='Cloud',
                    models=('nodeconductor.iaas.models.Cloud',
                            'nodeconductor.iaas.models.CloudProjectMembership',
                            'nodeconductor.iaas.models.OpenStackSettings',
                            )
                ),
                modules.ModelList(
                    title='Network',
                    models=('nodeconductor.iaas.models.FloatingIP',
                            'nodeconductor.iaas.models.IpMapping',
                            'nodeconductor.iaas.models.SecurityGroup',
                            )
                ),
            ]
        ))

        billing_models = ['nodeconductor.cost_tracking.*']
        if NodeConductorExtension.is_installed('nodeconductor_killbill'):
            billing_models.append('nodeconductor_killbill.models.Invoice')
        if NodeConductorExtension.is_installed('nodeconductor_paypal'):
            billing_models.append('nodeconductor_paypal.models.Payment')

        self.children.append(AppIconList(_('Billing'), models=billing_models))
        self.children.append(AppIconList(_('Structure'), models=(
            'nodeconductor.structure.*',
            'nodeconductor.core.models.User',
        )))

    def init_with_context(self, context):
        self.children.append(modules.LinkList(
            _('Installed components'),
            layout='stacked',
            draggable=True,
            deletable=True,
            collapsible=True,
            children=self._get_installed_plugin_info()
        ))


class CustomAppIndexDashboard(FluentAppIndexDashboard):
    def __init__(self, app_title, models, **kwargs):
        super(CustomAppIndexDashboard, self).__init__(app_title, models, **kwargs)
        path = self._get_app_models_path()
        self.children = [modules.ModelList(title=app_title, models=[path])]

    def _get_app_models_path(self):
        return '%s.models.*' % self.app_title.replace(' ', '.', 1).replace(' ', '_').lower()
