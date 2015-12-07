import json

from celery import chain
from django import template as django_template
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from jsonfield import JSONField
from model_utils.models import TimeStampedModel
import requests
from rest_framework import reverse
from rest_framework.authtoken.models import Token
from taggit.managers import TaggableManager

from nodeconductor.core import models as core_models
from nodeconductor.structure import models as structure_models


@python_2_unicode_compatible
class TemplateGroup(core_models.UuidMixin, core_models.UiDescribableMixin, models.Model):
    """ Group of resource templates that will be provisioned one by one """
    # Model doesn't inherit NameMixin, because name field must be unique.
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    tags = TaggableManager()

    def __str__(self):
        return self.name

    def schedule_head_template_provision(self, request, templates_additional_options):
        """ Send request that will schedule group first template provision """
        first_template = self.templates.order_by('order_number').first()
        url = first_template.get_provison_url(request)
        token_key = Token.objects.get(user=request.user).key
        additional_options = templates_additional_options.get(first_template, {})
        return first_template.schedule_provision(url, token_key, additional_options, ignore_provision_errors=True)

    def schedule_tail_templates_provision(self, request, templates_additional_options,
                                          first_template_provision_response):
        """ Start provision of group templates and return corresponding template group result.

        For head template method create only wait task, because provision has to scheduled previously.

        For other templates method creates 2 tasks each:
         - schedule_provision task - executes API request for resource provision
         - wait task - polls resource state and wait until it become "Online"

        All current group execution status is tracked in TemplateGroupResult instance that is returned as method result
        """
        from . import tasks

        templates_tasks = []
        template_group_result = TemplateGroupResult.objects.create(group=self)
        token_key = Token.objects.get(user=request.user).key
        # Define wait task for head templates
        first_template = self.templates.order_by('order_number').first()
        wait_task = tasks.wait_for_provision.si(
            previous_task_data=first_template_provision_response.json(),
            template_uuid=first_template.uuid.hex,
            token_key=token_key,
            template_group_result_uuid=template_group_result.uuid.hex)
        templates_tasks += [wait_task]
        # Define provision and wait tasks for other templates
        for template in self.templates.order_by('order_number')[1:]:
            url = template.get_provison_url(request)
            additional_options = templates_additional_options.get(template, {})
            additional_options = template.options.update(additional_options)
            schedule_provision_task = tasks.schedule_provision.s(
                url=url,
                template_uuid=template.uuid.hex,
                token_key=token_key,
                additional_options=additional_options,
                template_group_result_uuid=template_group_result.uuid.hex)
            wait_task = tasks.wait_for_provision.s(
                template_uuid=template.uuid.hex,
                token_key=token_key,
                template_group_result_uuid=template_group_result.uuid.hex)
            templates_tasks += [schedule_provision_task, wait_task]
        # Schedule tasks execution
        chain(*templates_tasks).apply_async(
            link=tasks.template_group_execution_succeed.si(template_group_result_uuid=template_group_result.uuid.hex),
            link_error=tasks.template_group_execution_failed.s(
                template_group_result_uuid=template_group_result.uuid.hex),
        )

        return template_group_result


class TemplateActionException(Exception):
    """ Exception that describes action human readable message and details for debugging

        Supports serialization for celery:
         - stores exception details and message into serialized json and stores it as Exception message
           (celery stores only exception message on serialization)
         - provides method to deserialize original message and details
    """

    def __init__(self, message, details):
        self.message = message
        self.details = details
        super(TemplateActionException, self).__init__(self.serialize())

    def serialize(self):
        return json.dumps({'message': self.message, 'details': self.details})

    @classmethod
    def deserialize(cls, serialized_exception):
        try:
            return json.loads(str(serialized_exception))
        except ValueError:
            return {'message': str(serialized_exception)}


@python_2_unicode_compatible
class Template(core_models.UuidMixin, models.Model):
    """ Template for application action.

        Currently templates application supports only resource provision actions.
        Describes instance default parameters.
    """
    group = models.ForeignKey(TemplateGroup, related_name='templates')
    options = JSONField(default={}, help_text='Default options for resource provision request.')
    tags = TaggableManager()
    service_settings = models.ForeignKey(structure_models.ServiceSettings, related_name='templates', null=True)
    resource_content_type = models.ForeignKey(
        ContentType, help_text='Content type of resource which provision process is described in template.')
    order_number = models.PositiveSmallIntegerField(
        default=1, help_text='Templates in group are sorted by order number. '
                             'Template with smaller order number will be executed first.')
    use_previous_resource_project = models.BooleanField(
        default=False, help_text='If True and project is not defined in template - current resource will use the same '
                                 'project as previous created.')

    def get_provison_url(self, request):
        model_class = self.resource_content_type.model_class()
        return reverse.reverse('%s-list' % model_class.get_url_name(), request=request)

    def schedule_provision(self, url, token_key, additional_options=None, previous_template_data=None,
                           ignore_provision_errors=False):
        """ Prepare request options and issue POST request for resource provision """
        headers = {'Authorization': 'Token %s' % token_key}
        # prepare request data: get default data and override it with user data
        options = self.options.copy()
        options.update(additional_options or {})

        # prepare request data: insert previous execution response variables as context to request data.
        # Example: {{ response.state }} will be replaced with real state field of previous execution response.
        if previous_template_data is not None:
            context = django_template.Context({'response': previous_template_data})
            for key, value in options.items():
                options[key] = django_template.Template(value).render(context)

        # prepare request data: use project from previous_template_data if <use_previous_resource_project> is True
        if self.use_previous_resource_project and not options.get('project'):
            options['project'] = previous_template_data['project']

        # prepare request data: get service if service settings and project are defined in options
        if options.get('project') and options.get('service_settings'):
            project_url = options.get('project')
            service_settings_url = options.pop('service_settings')
            project_services = self._get_project_services(project_url, headers)
            try:
                service_url = next((s['url'] for s in project_services if s['settings'] == service_settings_url))
            except StopIteration:
                details = 'There is no service connected to project "%s" based on service settings "%s"' % (
                    project_url, service_settings_url)
                raise TemplateActionException('Cannot find suitable service'. details)
            options['service'] = service_url

        # prepare request data: get SPL if service and project are defined in options
        if options.get('project') and options.get('service'):
            service_url = options.pop('service')
            project_url = options.pop('project')
            project_services = self._get_project_services(project_url, headers)
            try:
                spl_url = next((s['service_project_link_url'] for s in project_services if s['url'] == service_url))
            except StopIteration:
                details = 'Failed to find connection between project "%s" and service "%s" ' % (
                          project_url, service_url)
                raise TemplateActionException('Cannot find suitable SPL', details)
            options['service_project_link'] = spl_url

        # execute post request
        response = requests.post(url, headers=headers, json=options, verify=False)
        if not response.ok and not ignore_provision_errors:
            ct = self.resource_content_type
            message = 'Failed to schedule %s %s provision.' % (ct.app_label, ct.model)
            details = (
                'POST request to URL %s failed. Request body - %s. Response code - %s, content - %s' %
                (response.request.url, response.request.body, response.status_code, response.content))
            raise TemplateActionException(message, details)

        return response

    def _get_project_services(self, project_url, headers):
        response = requests.get(project_url, headers=headers, verify=False)
        if not response.ok:
            details = ('Failed get SPL from project. URL: "%s", response code - %s, '
                       'response content - %s' % (project_url, response.status_code, response.content))
            raise TemplateActionException('Cannot get project details', details)
        return response.json()['services']

    def get_resource(self, url, token_key):
        response = requests.get(url, headers={'Authorization': 'Token %s' % token_key}, verify=False)
        if not response.ok:
            ct = self.resource_content_type
            message = 'Failed to get %s %s state.' % (ct.app_label, ct.model)
            details = 'GET request to URL %s failed. Response code - %s, content - %s' % (
                      response.request.url, response.status_code, response.content)
            raise TemplateActionException(message, details, response.status_code)
        return response

    def __str__(self):
        return "%s -> %s" % (self.group.name, self.resource_content_type)


class TemplateGroupResult(core_models.UuidMixin, TimeStampedModel):
    """ Result of template group execution """
    group = models.ForeignKey(TemplateGroup, related_name='results')
    is_finished = models.BooleanField(default=False)
    is_erred = models.BooleanField(default=False)
    provisioned_resources = JSONField(default={})

    state_message = models.CharField(
        max_length=255, blank=True, help_text='Human readable description of current state of execution process.')
    error_message = models.CharField(
        max_length=255, blank=True, help_text='Human readable description of error.')
    error_details = models.TextField(blank=True, help_text='Error technical details.')
