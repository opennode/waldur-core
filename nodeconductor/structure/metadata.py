from collections import OrderedDict

from django.utils.encoding import force_text
from rest_framework import exceptions
from rest_framework.exceptions import PermissionDenied
from rest_framework.metadata import SimpleMetadata

from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.structure import SupportedServices


class ActionSerializer(object):
    def __init__(self, func, name, request, resource):
        self.func = func
        self.name = name
        self.request = request
        self.resource = resource

    def serialize(self):
        reason = self.get_reason()

        return {
            'title': self.get_title(),
            'method': self.get_method(),
            'destructive': self.is_destructive(),
            'url': self.get_url(),
            'reason': reason,
            'enabled': not reason
        }

    def is_destructive(self):
        return getattr(self.func, 'destructive', False)

    def get_title(self):
        try:
            return getattr(self.func, 'title')
        except AttributeError:
            return self.name.replace('_', ' ').title()

    def get_reason(self):
        valid_state = None
        if hasattr(self.func, 'valid_state'):
            valid_state = getattr(self.func, 'valid_state')

        try:
            check_operation(self.request.user, self.resource, self.name, valid_state)
        except exceptions.APIException as e:
            return force_text(e)

    def get_method(self):
        return getattr(self.func, 'method', 'POST')

    def get_url(self):
        base_url = self.request.build_absolute_uri()
        method = self.get_method()
        return method == 'DELETE' and base_url or base_url + self.name + '/'


class ResourceActionsMetadata(SimpleMetadata):
    """
    Difference from SimpleMetadata class:
    1) Skip read-only fields, because options are used only for provisioning new resource.
    2) Don't expose choices for fields with queryset in order to reduce size of response.
    3) Attach actions metadata
    """
    def determine_metadata(self, request, view):
        self.request = request
        metadata = OrderedDict()
        if view.lookup_field in view.kwargs:
            metadata['actions'] = self.get_actions(request, view)
        else:
            metadata['actions'] = self.determine_actions(request, view)
        return metadata

    def get_actions(self, request, view):
        """
        Return metadata for resource-specific actions,
        such as start, stop, unlink
        """
        metadata = OrderedDict()
        model = view.get_queryset().model
        actions = SupportedServices.get_resource_actions(model)
        resource = view.get_object()
        for name, action in actions.items():
            data = ActionSerializer(action, name, request, resource)
            metadata[name] = data.serialize()
            fields = self.get_action_fields(view, name)
            if not fields:
                metadata[name]['type'] = 'button'
            else:
                metadata[name]['type'] = 'form'
                metadata[name]['fields'] = fields
        return metadata

    def get_action_fields(self, view, name):
        """
        Get fields exposed by action's serializer
        """
        view.action = name
        serializer_class = view.get_serializer_class()
        fields = OrderedDict()
        if serializer_class and serializer_class != view.serializer_class:
            fields = self.get_fields(serializer_class._declared_fields)
        view.action = None
        return fields

    def get_serializer_info(self, serializer):
        """
        Given an instance of a serializer, return a dictionary of metadata
        about its fields.
        """
        if hasattr(serializer, 'child'):
            # If this is a `ListSerializer` then we want to examine the
            # underlying child serializer instance instead.
            serializer = serializer.child
        return self.get_fields(serializer.fields)

    def get_fields(self, serializer_fields):
        """
        Get fields metadata skipping empty fields
        """
        fields = OrderedDict()
        for field_name, field in serializer_fields.items():
            info = self.get_field_info(field, field_name)
            if info:
                fields[field_name] = info
        return fields

    def get_field_info(self, field, field_name):
        """
        Given an instance of a serializer field, return a dictionary
        of metadata about it.
        """
        field_info = OrderedDict()
        field_info['type'] = self.label_lookup[field]
        field_info['required'] = getattr(field, 'required', False)

        attrs = [
            'label', 'help_text',
            'min_length', 'max_length',
            'min_value', 'max_value', 'many'
        ]

        if getattr(field, 'read_only', False):
            return None

        for attr in attrs:
            value = getattr(field, attr, None)
            if value is not None and value != '':
                field_info[attr] = force_text(value, strings_only=True)

        if 'label' not in field_info:
            field_info['label'] = field_name.replace('_', ' ').title()

        choices_view = getattr(field, 'choices_view', None)
        if choices_view:
            field_info['type'] = 'select'
            field_info['url'] = self.request.build_absolute_uri() + choices_view + '/'

        if hasattr(field, 'choices') and not hasattr(field, 'queryset'):
            field_info['choices'] = [
                {
                    'value': choice_value,
                    'display_name': force_text(choice_name, strings_only=True)
                }
                for choice_value, choice_name in field.choices.items()
            ]

        return field_info


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
