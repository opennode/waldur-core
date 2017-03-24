from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from fluent_dashboard.dashboard import modules, FluentIndexDashboard, FluentAppIndexDashboard
from fluent_dashboard.modules import AppIconList

from nodeconductor.core import NodeConductorExtension, models as core_models
from nodeconductor.structure import models as structure_models, SupportedServices
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
        """
        Returns a list of ListLink items to be added to Quick Access tab.
        Contains:
        - a link to Organizations, Projects and Users;
        - a link to shared service settings;
        - a link to shared service settings in ERRED state if any;
        - custom configured links in admin/settings FLUENT_DASHBOARD_QUICK_ACCESS_LINKS attribute;
        - a list of links to resources in erred state and linked to shared service settings if there any in such state.
        """
        quick_access_links = []

        # add custom links
        quick_access_links.extend(settings.FLUENT_DASHBOARD_QUICK_ACCESS_LINKS)

        for model in (structure_models.Project, structure_models.Customer, core_models.User):
            quick_access_links.append(self._get_link_to_model(model))

        shared_service_setttings = self._get_link_to_model(structure_models.ServiceSettings)
        erred_shared_service_settings = shared_service_setttings.copy()
        shared_service_setttings['url'] = shared_service_setttings['url'] + '?shared__exact=1'
        shared_service_setttings['title'] = _('Shared service settings')
        quick_access_links.append(shared_service_setttings)

        erred_state = core_models.StateMixin.States.ERRED
        erred_shared_service_settings['url'] = shared_service_setttings['url'] + '&state__exact=' + str(erred_state)
        settings_in_erred_state = structure_models.ServiceSettings.objects.filter(state=erred_state).count()
        if settings_in_erred_state:
            erred_settings_title = '{0} {1}'.format(settings_in_erred_state, 'shared service settings in ERRED state')
            erred_shared_service_settings['title'] = erred_settings_title
            quick_access_links.append(erred_shared_service_settings)

        resource_models = SupportedServices.get_resource_models()
        for resource_type, resource_model in resource_models.items():
            erred_amount = resource_model.objects.filter(state=erred_state).count()
            if erred_amount:
                link = self._get_erred_resource_link(resource_model, erred_amount, erred_state)
                quick_access_links.append(link)

        return quick_access_links

    def _get_erred_resource_link(self, model, erred_amount, erred_state):
        result = self._get_link_to_model(model)
        result['title'] = '{0} {1} in ERRED state'.format(erred_amount, result['title'])
        result['url'] = '{0}?shared=1&state__exact={1}'.format(result['url'], erred_state)
        return result

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
