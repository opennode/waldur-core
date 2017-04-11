from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from fluent_dashboard.dashboard import modules, FluentIndexDashboard, FluentAppIndexDashboard
from fluent_dashboard.modules import AppIconList

from nodeconductor import __version__
from nodeconductor.core import NodeConductorExtension, models as core_models
from nodeconductor.structure import models as structure_models, SupportedServices, admin as structure_admin


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
                'attrs': {'target': '_blank'},
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
        - links to Organizations, Projects and Users;
        - a link to shared service settings;
        - custom configured links in admin/settings FLUENT_DASHBOARD_QUICK_ACCESS_LINKS attribute;
        """
        quick_access_links = []

        # add custom links
        quick_access_links.extend(settings.FLUENT_DASHBOARD_QUICK_ACCESS_LINKS)

        for model in (structure_models.Project,
                      structure_models.Customer,
                      core_models.User,
                      structure_admin.SharedServiceSettings):
            quick_access_links.append(self._get_link_to_model(model))

        return quick_access_links

    def _get_erred_resource_link(self, model, erred_amount, erred_state):
        result = self._get_link_to_model(model)
        result['title'] = '%s %s in ERRED state' % (erred_amount, result['title'])
        result['url'] = '%s?shared__exact=1&state__exact=%s' % (result['url'], erred_state)
        return result

    def _get_link_to_model(self, model):
        return {
            'title': str(model._meta.verbose_name_plural).capitalize(),
            'url': reverse("admin:%s_%s_changelist" % (model._meta.app_label, model._meta.model_name)),
            'external': True,
            'attrs': {'target': '_blank'},
        }

    def _get_link_to_instance(self, instance):
        return {
            'title': str(instance),
            'url': reverse("admin:%s_%s_change" % (instance._meta.app_label, instance._meta.model_name),
                           args=(instance.pk,)),
            'external': True,
            'attrs': {'target': '_blank'},
        }

    def _get_erred_shared_settings_module(self):
        """
        Returns a LinkList based module which contains link to shared service setting instances in ERRED state.
        """
        result_module = modules.LinkList(title='Shared service settings in erred state')
        result_module.template = 'admin/dashboard/erred_link_list.html'
        erred_state = structure_admin.SharedServiceSettings.States.ERRED

        queryset = structure_admin.SharedServiceSettings.objects
        settings_in_erred_state = queryset.filter(state=erred_state).count()

        if settings_in_erred_state:
            result_module.title = '%s (%s)' % (result_module.title, settings_in_erred_state)
            for settings in queryset.filter(state=erred_state).iterator():
                module_child = self._get_link_to_instance(settings)
                module_child['error'] = settings.error_message
                result_module.children.append(module_child)
        else:
            result_module.pre_content = 'Nothing found.'

        return result_module

    def _get_erred_resources_module(self):
        """
        Returns a list of links to resources which are in ERRED state and linked to a shared service settings.
        """
        result_module = modules.LinkList(title='Resources in erred state')
        erred_state = structure_models.NewResource.States.ERRED
        children = []

        resource_models = SupportedServices.get_resource_models()
        resources_in_erred_state_overall = 0
        for resource_type, resource_model in resource_models.items():
            queryset = resource_model.objects.filter(service_project_link__service__settings__shared=True)
            erred_amount = queryset.filter(state=erred_state).count()
            if erred_amount:
                resources_in_erred_state_overall = resources_in_erred_state_overall + erred_amount
                link = self._get_erred_resource_link(resource_model, erred_amount, erred_state)
                children.append(link)

        if resources_in_erred_state_overall:
            result_module.title = '%s (%s)' % (result_module.title, resources_in_erred_state_overall)
            result_module.children = children
        else:
            result_module.pre_content = 'Nothing found.'

        return result_module

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
            enabled=False,
            draggable=True,
            deletable=True,
            collapsible=True,
            children=self._get_installed_plugin_info()
        ))

        self.children.append(modules.LinkList(
            _('Quick access'),
            children=self._get_quick_access_info())
        )

        self.children.append(self._get_erred_shared_settings_module())
        self.children.append(self._get_erred_resources_module())


class CustomAppIndexDashboard(FluentAppIndexDashboard):
    def __init__(self, app_title, models, **kwargs):
        super(CustomAppIndexDashboard, self).__init__(app_title, models, **kwargs)
        path = self._get_app_models_path()
        self.children = [modules.ModelList(title=app_title, models=[path])]

    def _get_app_models_path(self):
        return '%s.models.*' % self.app_title.replace(' ', '.', 1).replace(' ', '_').lower()
