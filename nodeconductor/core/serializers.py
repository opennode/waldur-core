from django.contrib.auth import authenticate
from rest_framework import serializers

from nodeconductor.structure.filters import filter_queryset_for_user


class AuthTokenSerializer(serializers.Serializer):
    """
    Api token serializer loosely based on DRF's default AuthTokenSerializer,
    but with the response text and aligned with BasicAuthentication behavior.
    """
    username = serializers.CharField(required=True, blank=False)
    password = serializers.CharField(required=True, blank=False)

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