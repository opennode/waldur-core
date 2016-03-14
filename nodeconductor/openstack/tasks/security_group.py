import logging

from celery import shared_task, chain, Task
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.utils import six
from django_fsm import TransitionNotAllowed

from nodeconductor.core.tasks import transition, StateChangeError
from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import Instance, SecurityGroup, OpenStackServiceProjectLink


logger = logging.getLogger(__name__)


class BaseExecutor(object):

    @classmethod
    def get_tasks(cls, serialized_instance, **kwargs):
        raise NotImplementedError('Executor %s should implement method `get_tasks`' % cls.__name__)

    @classmethod
    def get_link(cls, serialized_instance, **kwargs):
        raise NotImplementedError('Executor %s should implement method `get_link`' % cls.__name__)

    @classmethod
    def get_link_error(cls, serialized_instance, **kwargs):
        raise NotImplementedError('Executor %s should implement method `get_link_error`' % cls.__name__)

    @classmethod
    def serialize_kwargs(cls, **kwargs):
        return kwargs

    @classmethod
    def execute(cls, instance, async=True, **kwargs):
        serialized_instance = LowLevelTask.serialize_instance(instance)
        kwargs = cls.serialize_kwargs(**kwargs)

        tasks = cls.get_tasks(serialized_instance, **kwargs)
        link = cls.get_link(serialized_instance, **kwargs),
        link_error = cls.get_link_error(serialized_instance, **kwargs)

        if async:
            result = tasks.apply_async(link=link, link_error=link_error)
        else:
            result = tasks.apply()
            if not result.failed():
                link.apply()
            else:
                link_error.apply()
        return result


class SynchronizableInstanceExecutor(BaseExecutor):

    @classmethod
    def get_link(cls, serialized_instance, **kwargs):
        return StateTransitionTask().si(serialized_instance, state_transition='set_in_sync')

    @classmethod
    def get_link_error(cls, serialized_instance, **kwargs):
        return StateTransitionTask().si(serialized_instance, state_transition='set_erred')


class LowLevelTask(Task):

    @staticmethod
    def serialize_instance(instance):
        return '%s:%s' % (ContentType.objects.get_for_model(instance).pk, instance.pk)

    def deserilize_instance(self, serialized_instance):
        content_type_pk, instance_pk = serialized_instance.split(':')
        ct = ContentType.objects.get(pk=content_type_pk)
        return ct.model_class().objects.get(pk=instance_pk)

    def run(self, serialized_instance, *args, **kwargs):
        instance = self.deserilize_instance(serialized_instance)
        return self.execute(instance, *args, **kwargs)

    def execute(self, instance, *args, **kwargs):
        raise NotImplementedError('LowLevelTask %s should implement method `execute`' % self.__class__.__name__)


class StateTransitionTask(LowLevelTask):

    def state_transition(self, instance, transition_method):
        instance_description = '%s instance `%s` (PK: %s)' % (instance.__class__.__name__, instance, instance.pk)
        old_state = instance.human_readable_state
        try:
            getattr(instance, transition_method)()
            instance.save(update_fields=['state'])
        except IntegrityError:
            message = (
                'Could not change state of %s, using method `%s` due to concurrent update' %
                (instance_description, transition_method))
            six.reraise(StateChangeError, StateChangeError(message))
        except TransitionNotAllowed:
            message = (
                'Could not change state of %s, using method `%s`. Current instance state: %s.' %
                (instance_description, transition_method, instance.human_readable_state))
            six.reraise(StateChangeError, StateChangeError(message))
        else:
            logger.info('State of instance changed from %s to %s, with method `%s`',
                        old_state, instance.human_readable_state, transition_method)

    def execute(self, instance, state_transition=None):
        if state_transition is not None:
            self.state_transition(instance, state_transition)


class BackendMethodTask(StateTransitionTask):

    def get_backend(self, instance):
        return instance.get_backend()

    def execute(self, instance, backend_method, state_transition=None, **kwargs):
        if state_transition is not None:
            self.state_transition(instance, state_transition)
        backend = self.get_backend(instance)
        return getattr(backend, backend_method)(instance, **kwargs)


class SecurityGroupSingleTaskExecutor(SynchronizableInstanceExecutor):

    @classmethod
    def get_tasks(self, security_group, **kwargs):
        return BackendMethodTask().si(security_group, 'test_security_group_method', state_transition='begin_syncing')


class SecurityGroupChainExecutor(SynchronizableInstanceExecutor):

    @classmethod
    def get_tasks(self, security_group, **kwargs):
        return chain(
            BackendMethodTask().si(security_group, 'test_security_group_method', state_transition='begin_syncing'),
            BackendMethodTask().si(security_group, 'test_security_group_method'),
        )


@shared_task(name='nodeconductor.openstack.sync_instance_security_groups')
def sync_instance_security_groups(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    backend = instance.get_backend()
    backend.sync_instance_security_groups(instance)


@shared_task(name='nodeconductor.openstack.create_security_group')
@transition(SecurityGroup, 'begin_syncing')
def create_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_create_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.openstack.update_security_group')
@transition(SecurityGroup, 'begin_syncing')
def update_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_update_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.openstack.delete_security_group')
@transition(SecurityGroup, 'begin_syncing')
def delete_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_delete_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_deletion_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task
@transition(SecurityGroup, 'set_in_sync')
def security_group_sync_succeeded(security_group_uuid, transition_entity=None):
    pass


@shared_task
@transition(SecurityGroup, 'set_erred')
def security_group_sync_failed(security_group_uuid, transition_entity=None):
    pass


@shared_task
def security_group_deletion_succeeded(security_group_uuid):
    SecurityGroup.objects.filter(uuid=security_group_uuid).delete()


@shared_task
def openstack_create_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.create_security_group(security_group)


@shared_task
def openstack_update_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.update_security_group(security_group)


@shared_task
def openstack_delete_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.delete_security_group(security_group)


@shared_task(name='nodeconductor.openstack.openstack_pull_security_groups')
def openstack_pull_security_groups(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        backend.pull_security_groups(service_project_link)
    except OpenStackBackendError:
        logger.warning("Failed to pull security groups for service project link %s.",
                       service_project_link_str)


@shared_task(name='nodeconductor.openstack.openstack_push_security_groups')
def openstack_push_security_groups(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        backend.push_security_groups(service_project_link)
    except OpenStackBackendError:
        logger.warning("Failed to push security groups for service project link %s.",
                       service_project_link_str)
