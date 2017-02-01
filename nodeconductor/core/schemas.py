from collections import OrderedDict

from django.utils.encoding import smart_text
from rest_framework import exceptions, schemas, serializers
from rest_framework.permissions import AllowAny, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.utils import formatting
from rest_framework.views import APIView
from rest_framework_swagger import renderers

from permissions import ActionsPermission
from views import ActionsViewSet


# XXX: Drop after removing HEAD requests
class WaldurEndpointInspector(schemas.EndpointInspector):
    def get_allowed_methods(self, callback):
        """
        Return a list of the valid HTTP methods for this endpoint.
        """
        if hasattr(callback, 'actions'):
            return [method.upper() for method in callback.actions.keys() if method != 'head']

        return [
            method for method in
            callback.cls().allowed_methods if method not in ('OPTIONS', 'HEAD')
        ]


def get_entity_description(entity):
    """
    Returns description in format:
    * entity human readable name
     * docstring
    """

    try:
        entity_name = entity.__name__.strip('_')
    except AttributeError:
        # entity is a class instance
        entity_name = entity.__class__.__name__

    label = '* %s' % formatting.camelcase_to_spaces(entity_name)
    if entity.__doc__ is not None:
        entity_docstring = formatting.dedent(smart_text(entity.__doc__)).replace('\n', '\n\t')
        return '%s\n * %s' % (label, entity_docstring)

    return label


def get_validators_description(view):
    """
    Returns validators description in format:
    ### Validators:
    * validator1 name
     * validator1 docstring
    * validator2 name
     * validator2 docstring
    """
    action = getattr(view, 'action', None)
    if action is None:
        return ''

    description = ''
    validators = getattr(view, action + '_validators', [])
    for validator in validators:
        validator_description = get_entity_description(validator)
        description += '\n' + validator_description if description else validator_description

    return '### Validators:\n' + description if description else ''


def get_actions_permission_description(view, method):
    """
    Returns actions permissions description in format:
    * permission1 name
     * permission1 docstring
    * permission2 name
     * permission2 docstring
    """
    action = getattr(view, 'action', None)
    if action is None:
        return ''

    if hasattr(view, action + '_permissions'):
        permission_types = (action,)
    elif method in SAFE_METHODS:
        permission_types = ('safe_methods', '%s_extra' % action)
    else:
        permission_types = ('unsafe_methods', '%s_extra' % action)

    description = ''
    for permission_type in permission_types:
        permissions = getattr(view, permission_type + '_permissions', [])
        for permission in permissions:
            action_perm_description = get_entity_description(permission)
            description += '\n' + action_perm_description if description else action_perm_description

    return description


def get_permissions_description(view, method):
    """
    Returns permissions description in format:
    ### Permissions:
    * permission1 name
     * permission1 docstring
    * permission2 name
     * permission2 docstring
    """
    if not hasattr(view, 'permission_classes'):
        return ''

    description = ''
    for permission_class in view.permission_classes:
        if permission_class == ActionsPermission:
            actions_perm_description = get_actions_permission_description(view, method)
            if actions_perm_description:
                description += '\n' + actions_perm_description if description else actions_perm_description
            continue
        perm_description = get_entity_description(permission_class)
        description += '\n' + perm_description if description else perm_description

    return '### Permissions:\n' + description if description else ''


def get_validation_description(view, method):
    """
    Returns validation description in format:
    ### Validation:
    validate method docstring
    * field1 name
     * field1 validation docstring
    * field2 name
     * field2 validation docstring
    """
    if method not in ('PUT', 'PATCH', 'POST') or not hasattr(view, 'get_serializer'):
        return ''

    serializer = view.get_serializer()
    description = ''
    if hasattr(serializer, 'validate') and serializer.validate.__doc__ is not None:
        description += formatting.dedent(smart_text(serializer.validate.__doc__))

    for field in serializer.fields.values():
        if not hasattr(serializer, 'validate_' + field.field_name):
            continue

        field_validation = getattr(serializer, 'validate_' + field.field_name)

        if field_validation.__doc__ is not None:
            docstring = formatting.dedent(smart_text(field_validation.__doc__)).replace('\n', '\n\t')
            field_description = '* %s\n * %s' % (field.field_name, docstring)
            description += '\n' + field_description if description else field_description

    return '### Validation:\n' + description if description else ''


class WaldurSchemaGenerator(schemas.SchemaGenerator):
    endpoint_inspector_cls = WaldurEndpointInspector

    def get_links(self, request=None):
        """
        Return a dictionary containing all the links that should be
        included in the API schema.
        """
        links = OrderedDict()

        # Generate (path, method, view) given (path, method, callback).
        paths = []
        view_endpoints = []
        for path, method, callback in self.endpoints:
            view = self.create_view(callback, method, request)
            if getattr(view, 'exclude_from_schema', False):
                continue
            path = self.coerce_path(path, method, view)
            paths.append(path)
            view_endpoints.append((path, method, view))

        # Only generate the path prefix for paths that will be included
        if not paths:
            return None
        prefix = self.determine_path_prefix(paths)

        for path, method, view in view_endpoints:
            if not self.has_view_permissions(path, method, view):
                continue
            elif self.is_disabled_action(view):
                continue
            link = self.get_link(path, method, view)
            subpath = path[len(prefix):]
            keys = self.get_keys(subpath, method, view)
            schemas.insert_into(links, keys, link)
        return links

    def is_disabled_action(self, view):
        """
        Checks whether Link action is disabled.
        """
        if not isinstance(view, ActionsViewSet):
            return False

        action = getattr(view, 'action', None)
        return action in view.disabled_actions if action is not None else False

    def get_description(self, path, method, view):
        """
        Determine a link description.

        This will be based on the method docstring if one exists,
        or else the class docstring.
        """
        description = super(WaldurSchemaGenerator, self).get_description(path, method, view)

        permissions_description = get_permissions_description(view, method)
        if permissions_description:
            description += '\n\n' + permissions_description if description else permissions_description

        if isinstance(view, ActionsViewSet):
            validators_description = get_validators_description(view)
            if validators_description:
                description += '\n\n' + validators_description if description else validators_description

        validation_description = get_validation_description(view, method)
        if validation_description:
            description += '\n\n' + validation_description if description else validation_description

        return description


class WaldurSchemaView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [
        renderers.OpenAPIRenderer,
        renderers.SwaggerUIRenderer
    ]

    def get(self, request):
        generator = WaldurSchemaGenerator(
            title='Waldur MasterMind',
        )
        schema = generator.get_schema(request=request)

        if not schema:
            raise exceptions.ValidationError(
                'The schema generator did not return a schema Document'
            )

        return Response(schema)
