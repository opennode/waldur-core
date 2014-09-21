import base64

from django.contrib.auth import authenticate
from rest_framework import serializers

from nodeconductor.structure.filters import filter_queryset_for_user


class AuthTokenSerializer(serializers.Serializer):
    """
    Api token serializer loosely based on DRF's default AuthTokenSerializer,
    but with the response text and aligned with BasicAuthentication behavior.
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    def validate(self, attrs):
        # Since the fields are both required and non-blank
        # and field-validation is performed before object-level validation
        # it is safe to assume these dict keys present.
        username = attrs['username']
        password = attrs['password']

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError('Invalid username/password')

        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')
        attrs['user'] = user

        return attrs


class Base64Field(serializers.CharField):
    def from_native(self, value):
        value = super(Base64Field, self).from_native(value)
        try:
            return base64.b64decode(value)
        except TypeError:
            raise serializers.ValidationError("Enter valid Base64 encoded string.")

    def to_native(self, value):
        value = super(Base64Field, self).to_native(value)
        return base64.b64encode(value)


class Saml2ResponseSerializer(serializers.Serializer):
    saml2response = Base64Field(required=True)


class PermissionFieldFilteringMixin(object):
    """
    Mixin allowing to filter related fields.

    In order to constrain the list of entities that can be used
    as a value for the field:

    1. Make sure that the entity in question has corresponding
       Permission class defined.

    2. Implement `get_filtered_field_names()` method
       in the class that this mixin is mixed into and return
       the field in question from that method.
    """
    def get_fields(self):
        fields = super(PermissionFieldFilteringMixin, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        for field_name in self.get_filtered_field_names():
            fields[field_name].queryset = filter_queryset_for_user(
                fields[field_name].queryset, user)

        return fields

    def get_filtered_field_names(self):
        raise NotImplementedError(
            'Implement get_filtered_field_names() '
            'to return list of filtered fields')


class RelatedResourcesFieldMixin(object):
    """
    Mixin that adds fields describing related resources.

    For related resource Foo two fields are added:

    1. `foo` containing a URL to the Foo resource
    2. `foo_name` containing the name of the Foo resource

    In order to add related resource fields:

    1. Inherit from `RelatedResourcesFieldMixin`.

    2. Implement `get_related_paths()` method
       and return paths to related resources
       from the current resource.
    """
    def get_default_fields(self):
        fields = super(RelatedResourcesFieldMixin, self).get_default_fields()

        for path in self.get_related_paths():
            path_components = path.split('.')
            entity_name = path_components[-1]

            fields[entity_name] = serializers.HyperlinkedRelatedField(
                source=path,
                view_name='{0}-detail'.format(entity_name),
                lookup_field='uuid',
                read_only=len(path_components) > 1,
            )

            fields['{0}_name'.format(entity_name)] = serializers.Field(source='{0}.name'.format(path))

        return fields

    def get_related_paths(self):
        raise NotImplementedError(
            'Implement get_paths() to return list of filtered fields')