from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from fluent_dashboard.dashboard import modules, FluentIndexDashboard, FluentAppIndexDashboard
from fluent_dashboard.modules import AppIconList

from nodeconductor.core import NodeConductorExtension, models
from nodeconductor.structure import models as structure_models
from nodeconductor import __version__


class CustomIndexDashboard(FluentIndexDashboard):
    """
    Custom index dashboard for admin site.
    """
    title = 'Waldur administration'

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

    def _get_quick_access_info(self):
        default = []

        for model in (structure_models.Project, structure_models.Customer, models.User):
            default.append(self._get_link_to_model(model))

        shared_service_setttings = self._get_link_to_model(structure_models.ServiceSettings)
        erred_shared_service_settings = shared_service_setttings.copy()
        shared_service_setttings['url'] = shared_service_setttings['url'] + '?shared__exact=1'
        shared_service_setttings['title'] = _('Shared service settings')
        default.append(shared_service_setttings)

        erred_state = structure_models.ServiceSettings.States.ERRED
        erred_shared_service_settings['url'] = shared_service_setttings['url'] + '&state__exact=' + str(erred_state)
        settings_in_erred_state = structure_models.ServiceSettings.objects.filter(state=erred_state).count()
        erred_settings_title = '{0} {1}'.format(settings_in_erred_state, _('shared settings in ERRED state'))
        erred_shared_service_settings['title'] = erred_settings_title
        default.append(erred_shared_service_settings)

        return default

    def _get_link_to_model(self, model):
        return {
            'title': str(model._meta.verbose_name_plural).capitalize(),
            'url': reverse("admin:%s_%s_changelist" % (model._meta.app_label, model._meta.model_name)),
            'external': True,
        }

    def __init__(self, **kwargs):
        FluentIndexDashboard.__init__(self, **kwargs)

        billing_models = ['nodeconductor.cost_tracking.*']
        if NodeConductorExtension.is_installed('nodeconductor_killbill'):
            billing_models.append('nodeconductor_killbill.models.Invoice')
        if NodeConductorExtension.is_installed('nodeconductor_paypal'):
            billing_models.append('nodeconductor_paypal.models.Payment')

        self.children.append(AppIconList(_('Billing'), models=billing_models))

        self.children.append(modules.LinkList(
            _('Installed components'),
            layout='stacked',
            draggable=True,
            deletable=True,
            collapsible=True,
            children=self._get_installed_plugin_info()
        ))

        self.children.append(modules.LinkList(
            _('Quick access'),
            children=self._get_quick_access_info())
        )


class CustomAppIndexDashboard(FluentAppIndexDashboard):
    def __init__(self, app_title, models, **kwargs):
        super(CustomAppIndexDashboard, self).__init__(app_title, models, **kwargs)
        path = self._get_app_models_path()
        self.children = [modules.ModelList(title=app_title, models=[path])]

    def _get_app_models_path(self):
        return '%s.models.*' % self.app_title.replace(' ', '.', 1).replace(' ', '_').lower()
