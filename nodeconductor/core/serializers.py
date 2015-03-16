import base64

from django.contrib.auth import authenticate
from django.core import validators
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers
from rest_framework.fields import Field

from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.structure.filters import filter_queryset_for_user

validate_ipv4_address_within_list = validators.RegexValidator(
    validators.ipv4_re, 'Enter a list of valid IPv4 addresses.',
    'invalid')


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


class IPsField(serializers.CharField):
    def to_native(self, value):
        value = super(IPsField, self).to_native(value)
        if value is None:
            return []
        else:
            return [value]

    def from_native(self, value):
        if value in validators.EMPTY_VALUES:
            return None

        if not isinstance(value, (list, tuple)):
            raise validators.ValidationError('Enter a list of valid IPv4 addresses.')

        value_count = len(value)
        if value_count > 1:
            raise validators.ValidationError('Only one ip address is supported.')
        elif value_count == 1:
            value = value[0]
            validate_ipv4_address_within_list(value)
        else:
            value = None

        return value


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





class BasicInfoSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        fields = ('url', 'name')
        lookup_field = 'uuid'


class UnboundSerializerMethodField(Field):
    """
    A field that gets its value by calling a provided filter callback.
    """

    def __init__(self, filter_function, *args, **kwargs):
        self.filter_function = filter_function
        super(UnboundSerializerMethodField, self).__init__(*args, **kwargs)

    def field_to_native(self, obj, field_name):
        try:
            request = self.context['request']
        except KeyError:
            return self.to_native(obj)

        value = self.filter_function(obj, request)
        return self.to_native(value)


class AugmentedSerializerMixin(object):
    """
    This mixing provides several extensions to stock Serializer class:

    1.  Adding extra fields to serializer from dependent applications in a way
        that doesn't introduce circular dependencies.

        To achieve this, dependent application should subscribe
        to pre_serializer_fields signal and inject additional fields.

        Example of signal handler implementation:
            # handlers.py
            def add_customer_name(sender, fields, **kwargs):
                fields['customer_name'] = ReadOnlyField(source='customer.name')

            # apps.py
            class DependentAppConfig(AppConfig):
                name = 'nodeconductor.structure_dependent'
                verbose_name = "NodeConductor Structure Enhancements"

                def ready(self):
                    from nodeconductor.structure.serializers import CustomerSerializer

                    pre_serializer_fields.connect(
                        handlers.add_customer_name,
                        sender=CustomerSerializer,
                    )

    2.  Declaratively add attributes fields of related entities for ModelSerializers.

        To achieve list related fields whose attributes you want to include.

        Example:
            class ProjectSerializer(AugmentedSerializerMixin,
                                    serializers.HyperlinkedModelSerializer):
                class Meta(object):
                    model = models.Project
                    fields = (
                        'url', 'uuid', 'name',
                        'customer', 'customer_uuid', 'customer_name',
                    )
                    related_paths = ('customer',)

            # This is equivalent to listing the fields explicitly,
            # by default "uuid" and "name" fields of related object are added:

            class ProjectSerializer(AugmentedSerializerMixin,
                                    serializers.HyperlinkedModelSerializer):
                customer_uuid = serializers.ReadOnlyField(source='customer.uuid')
                customer_name = serializers.ReadOnlyField(source='customer.name')
                class Meta(object):
                    model = models.Project
                    fields = (
                        'url', 'uuid', 'name',
                        'customer', 'customer_uuid', 'customer_name',
                    )
                    lookup_field = 'uuid'

            # The fields of related object can be customized:

            class ProjectSerializer(AugmentedSerializerMixin,
                                    serializers.HyperlinkedModelSerializer):
                class Meta(object):
                    model = models.Project
                    fields = (
                        'url', 'uuid', 'name',
                        'customer', 'customer_uuid',
                        'customer_name', 'customer_native_name',
                    )
                    related_paths = {
                        'customer': ('uuid', 'name', 'native_name')
                    }

    """

    def get_fields(self):
        fields = super(AugmentedSerializerMixin, self).get_fields()
        pre_serializer_fields.send(sender=self.__class__, fields=fields)
        return fields

    def _get_related_paths(self):
        try:
            related_paths = self.Meta.related_paths
        except AttributeError:
            if callable(getattr(self, 'get_related_paths', None)):
                import warnings

                warnings.warn(
                    "get_related_paths() is deprecated. "
                    "Inherit from AugmentedSerializerMixin and set Meta.related_paths instead.",
                    DeprecationWarning,
                )
                related_paths = self.get_related_paths()
            else:
                return {}

        if not isinstance(self, serializers.ModelSerializer):
            raise ImproperlyConfigured(
                'related_paths can be defined only for ModelSerializer.'
            )

        if isinstance(related_paths, (list, tuple)):
            related_paths = {path: ('name', 'uuid') for path in related_paths}

        return related_paths

    def build_unknown_field(self, field_name, model_class):
        related_paths = self._get_related_paths()

        related_field_source_map = {
            '{0}_{1}'.format(path.split('.')[-1], attribute): '{0}.{1}'.format(path, attribute)
            for path, attributes in related_paths.items()
            for attribute in attributes
        }

        try:
            return serializers.ReadOnlyField, {'source': related_field_source_map[field_name]}
        except KeyError:
            return super(AugmentedSerializerMixin, self).build_unknown_field(field_name, model_class)


class CollectedFieldsMixin(AugmentedSerializerMixin):
    def __init__(self, *args, **kwargs):
        import warnings

        warnings.warn(
            "CollectedFieldsMixin is deprecated. "
            "Use AugmentedSerializerMixin instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        super(CollectedFieldsMixin, self).__init__(*args, **kwargs)


class RelatedResourcesFieldMixin(AugmentedSerializerMixin):
    def __init__(self, *args, **kwargs):
        import warnings

        warnings.warn(
            "RelatedResourcesFieldMixin is deprecated. "
            "Use AugmentedSerializerMixin instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        super(RelatedResourcesFieldMixin, self).__init__(*args, **kwargs)
