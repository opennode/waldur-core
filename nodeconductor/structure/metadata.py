from collections import OrderedDict

from django.utils import six
from django.utils.encoding import force_text
from rest_framework import serializers, exceptions
from rest_framework.exceptions import PermissionDenied
from rest_framework.metadata import SimpleMetadata
from rest_framework.reverse import reverse

from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.structure import SupportedServices


class ResourceActionsMetadata(SimpleMetadata):
    """
    Difference from SimpleMetadata class:
    1) Skip read-only fields, because options are used only for provisioning new resource.
    2) Don't expose choices for fields with queryset in order to reduce size of response.
    3) Attach actions metadata
    """
    def __init__(self):
        self.label_lookup[serializers.HyperlinkedRelatedField] = 'select_url'

    def determine_metadata(self, request, view):
        self.request = request
        metadata = OrderedDict()
        metadata['actions'] = self.get_actions_metadata(request, view)
        metadata['actions'].update(self.determine_actions(request, view))
        return metadata

    def get_actions_metadata(self, request, view):
        metadata = OrderedDict()
        model = view.get_queryset().model
        actions = SupportedServices.get_resource_actions(model)
        for name, action in actions.items():
            metadata[name] = {
                'title': self.get_action_title(action, name),
                'method': self.get_action_method(action),
                'destructive': self.is_action_destructive(action),
            }
            fields = self.get_action_fields(view, name)
            if not fields:
                metadata[name]['type'] = 'button'
            else:
                metadata[name]['type'] = 'form'
                metadata[name]['fields'] = fields
        return metadata

    def is_action_destructive(self, action):
        try:
            return getattr(action, 'destructive')
        except AttributeError:
            return False

    def get_action_title(self, action, name):
        try:
            return getattr(action, 'title')
        except AttributeError:
            return name.replace('_', ' ').title()

    def get_action_fields(self, view, name):
        view.action = name
        serializer_class = view.get_serializer_class()
        fields = OrderedDict()
        if serializer_class and serializer_class != view.serializer_class:
            for field_name, field in serializer_class._declared_fields.items():
                info = self.get_field_info(field)
                if info:
                    fields[field_name] = info
        view.action = None
        return fields

    def get_action_method(self, action):
        return getattr(action, 'method', 'POST')

    def get_serializer_info(self, serializer):
        """
        Given an instance of a serializer, return a dictionary of metadata
        about its fields.
        """
        if hasattr(serializer, 'child'):
            # If this is a `ListSerializer` then we want to examine the
            # underlying child serializer instance instead.
            serializer = serializer.child
        fields = OrderedDict()
        for field_name, field in serializer.fields.items():
            info = self.get_field_info(field)
            if info:
                fields[field_name] = info
        return fields

    def get_field_info(self, field):
        """
        Given an instance of a serializer field, return a dictionary
        of metadata about it.
        """
        field_info = OrderedDict()
        field_info['type'] = self.label_lookup[field]
        field_info['required'] = getattr(field, 'required', False)

        attrs = [
            'read_only', 'label', 'help_text',
            'min_length', 'max_length',
            'min_value', 'max_value', 'many'
        ]

        for attr in attrs:
            value = getattr(field, attr, None)
            if value is not None and value != '':
                field_info[attr] = force_text(value, strings_only=True)

        if 'read_only' in field_info:
            if field_info['read_only']:
                return None
            del field_info['read_only']

        if isinstance(field, serializers.HyperlinkedRelatedField):
            list_view = field.view_name.replace('-detail', '-list')
            field_info['url'] = reverse(list_view, request=self.request)

        if hasattr(field, 'choices') and not hasattr(field, 'queryset'):
            field_info['choices'] = [
                {
                    'value': choice_value,
                    'display_name': force_text(choice_name, strings_only=True)
                }
                for choice_value, choice_name in field.choices.items()
            ]

        return field_info


def get_actions_for_resource(user, resource):
    metadata = []

    def get_info(name, valid_state=None):
        enabled = True
        reason = None
        try:
            check_operation(user, resource, name, valid_state)
        except exceptions.APIException as e:
            enabled = False
            reason = six.text_type(e)
        return {
            'name': name,
            'enabled': enabled,
            'reason': reason
        }

    actions = SupportedServices.get_resource_actions(resource)
    for name, action in actions.items():
        valid_state = None
        if hasattr(action, 'valid_state'):
            valid_state = getattr(action, 'valid_state')
        info = get_info(name, valid_state)
        metadata.append(info)

    return metadata


# TODO: Allow to define permissions based on user and object
def check_operation(user, resource, operation_name, valid_state=None):
    from nodeconductor.structure import models

    project = resource.service_project_link.project
    is_admin = project.has_user(user, models.ProjectRole.ADMINISTRATOR) \
        or project.customer.has_user(user, models.CustomerRole.OWNER)

    if not is_admin and not user.is_staff:
        raise PermissionDenied(
            "Only project administrator or staff allowed to perform this action.")

    if valid_state is not None:
        state = valid_state if isinstance(valid_state, (list, tuple)) else [valid_state]
        if state and resource.state not in state:
            message = "Performing %s operation is not allowed for resource in its current state"
            raise IncorrectStateException(message % operation_name)
