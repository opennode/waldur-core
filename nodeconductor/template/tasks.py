from celery import shared_task

from nodeconductor.core.tasks import retry_if_false
from nodeconductor.structure import SupportedServices
from nodeconductor.template import models


@shared_task
def schedule_provision(previous_task_data=None, url=None, template_uuid=None, token_key=None,
                       additional_options=None, template_group_result_uuid=None):
    template = models.Template.objects.get(uuid=template_uuid)
    response_data = template.schedule_provision(url, token_key, additional_options, previous_task_data).json()
    # update templates group result if it is defined
    if template_group_result_uuid is not None:
        template_group_result = models.TemplateGroupResult.objects.get(uuid=template_group_result_uuid)
        resource_type = SupportedServices.get_name_for_model(template.object_content_type.model_class())
        template_group_result.state_message = '%s provision has been scheduled successfully.' % resource_type
        template_group_result.save()
    return response_data


@shared_task(max_retries=120, default_retry_delay=20)
@retry_if_false
def wait_for_provision(previous_task_data=None, template_uuid=None, token_key=None,
                       template_group_result_uuid=None, success_states=['Online', 'OK'], erred_state='Erred'):
    template_group_result = models.TemplateGroupResult.objects.get(uuid=template_group_result_uuid)
    template = models.Template.objects.get(uuid=template_uuid)

    url = previous_task_data['url']
    resource_data = template.get_resource(url, token_key).json()

    resource_type = SupportedServices.get_name_for_model(template.object_content_type.model_class())
    template_group_result.provisioned_resources[resource_type] = url
    template_group_result.save()
    state = resource_data['state']
    if state in success_states:
        template_group_result.state_message = '%s has been successfully provisioned.' % resource_type
        template_group_result.save()
        return resource_data
    elif state != erred_state:
        template_group_result.state_message = 'Waiting for %s provision (current state: %s). ' % (resource_type, state)
        template_group_result.save()
        return False
    else:
        message = 'Failed to provision %s.' % resource_type
        details = 'Resource with URL %s come to state "%s".' % (url, state)
        raise models.TemplateActionException(message, details)


@shared_task
def template_group_execution_succeed(template_group_result_uuid):
    template_group_result = models.TemplateGroupResult.objects.get(uuid=template_group_result_uuid)
    template_group_result.state_message = 'Template group has been executed successfully.'
    template_group_result.is_finished = True
    template_group_result.save()


@shared_task(bind=True)
def template_group_execution_failed(self, task_uuid, template_group_result_uuid):
    task_result = self.app.AsyncResult(task_uuid)
    error = models.TemplateActionException.deserialize(str(task_result.result))
    template_group_result = models.TemplateGroupResult.objects.get(uuid=template_group_result_uuid)
    template_group_result.state_message = 'Execution of a template group has failed.'
    template_group_result.error_message = error['message']
    template_group_result.error_details = error.get('details', '')
    template_group_result.is_finished = True
    template_group_result.is_erred = True
    template_group_result.save()
