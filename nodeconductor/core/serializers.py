import base64

from django.core import validators
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.urlresolvers import reverse, resolve, Resolver404
from rest_framework import serializers
from rest_framework.fields import Field, ReadOnlyField

from nodeconductor.core.signals import pre_serializer_fields


class AuthTokenSerializer(serializers.Serializer):
    """
    Api token serializer loosely based on DRF's default AuthTokenSerializer.
    but with the logic of authorization is extracted to view.
    """
    # Fields are both required, non-blank and don't allow nulls by default
    username = serializers.CharField()
    password = serializers.CharField()


class Base64Field(serializers.CharField):
    def to_internal_value(self, data):
        value = super(Base64Field, self).to_internal_value(data)
        try:
            return base64.b64decode(value)
        except TypeError:
            raise serializers.ValidationError('This field should a be valid Base64 encoded string.')

    def to_representation(self, value):
        value = super(Base64Field, self).to_representation(value)
        return base64.b64encode(value)


# XXX: this field has to be replaced with default drf IPAddressField after it implementation:
# https://github.com/tomchristie/django-rest-framework/issues/1853

class IPAddressField(serializers.CharField):
    def __init__(self, **kwargs):
        super(IPAddressField, self).__init__(**kwargs)
        ip_validators, _ = validators.ip_address_validators(protocol='ipv4', unpack_ipv4=False)
        self.validators += ip_validators


class Saml2ResponseSerializer(serializers.Serializer):
    saml2response = Base64Field(required=True)


class BasicInfoSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        fields = ('url', 'name')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class UnboundSerializerMethodField(ReadOnlyField):
    """
    A field that gets its value by calling a provided filter callback.
    """

    def __init__(self, filter_function, *args, **kwargs):
        self.filter_function = filter_function
        super(UnboundSerializerMethodField, self).__init__(*args, **kwargs)

    def to_representation(self, value):
        request = self.context.get('request')
        return self.filter_function(value, request)


class GenericRelatedField(Field):
    """
    A custom field to use for the `tagged_object` generic relationship.
    """
    read_only = False
    _default_view_name = '%(model_name)s-detail'
    lookup_fields = ['uuid', 'pk']

    def __init__(self, related_models=(), **kwargs):
        super(GenericRelatedField, self).__init__(**kwargs)
        self.related_models = related_models

    def _get_url(self, obj):
        """
        Gets object url
        """
        format_kwargs = {
            'app_label': obj._meta.app_label,
        }
        try:
            format_kwargs['model_name'] = getattr(obj, 'DEFAULT_URL_NAME')
        except AttributeError:
            format_kwargs['model_name'] = obj._meta.object_name.lower()
        return self._default_view_name % format_kwargs

    def to_representation(self, obj):
        """
        Serializes any object to his url representation
        """
        kwargs = None
        for field in self.lookup_fields:
            if hasattr(obj, field):
                kwargs = {field: getattr(obj, field)}
                break
        if kwargs is None:
            raise AttributeError('Related object does not have any of of lookup_fields')
        try:
            request = self.context['request']
        except AttributeError:
            raise AttributeError('GenericRelatedField have to be initialized with `request` in context')
        return request.build_absolute_uri(reverse(self._get_url(obj), kwargs=kwargs))

    def _format_url(self, url):
        """
        Removes domain and protocol from url
        """
        if url.startswith('http'):
            return '/' + url.split('/', 3)[-1]
        return url

    def _get_model_from_resolve_match(self, match):
        queryset = match.func.cls.queryset
        if queryset is not None:
            return queryset.model
        else:
            return match.func.cls.model

    def to_internal_value(self, data):
        """
        Restores model instance from its url
        """
        try:
            url = self._format_url(data)
            match = resolve(url)
            model = self._get_model_from_resolve_match(match)
            obj = model.objects.get(**match.kwargs)
        except (Resolver404, AttributeError):
            raise ValidationError("Can`t restore object from url: %s" % data)
        if model not in self.related_models:
            raise ValidationError('%s object does not support such relationship' % str(obj))
        return obj


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

    3,  Protect some fields from change.

        Example:
            class ProjectSerializer(AugmentedSerializerMixin,
                                    serializers.HyperlinkedModelSerializer):
                class Meta(object):
                    model = models.Project
                    fields = ('url', 'uuid', 'name', 'customer')
                    protected_fields = ('customer',)

    """

    def get_fields(self):
        fields = super(AugmentedSerializerMixin, self).get_fields()
        pre_serializer_fields.send(sender=self.__class__, fields=fields)

        try:
            protected_fields = self.Meta.protected_fields
        except AttributeError:
            pass
        else:
            try:
                method = self.context['view'].request.method
            except (KeyError, AttributeError):
                return fields

            if method in ('PUT', 'PATCH'):
                for field in protected_fields:
                    fields[field].read_only = True

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


class HyperlinkedRelatedModelSerializer(serializers.HyperlinkedModelSerializer):
    def __init__(self, **kwargs):
        self.queryset = kwargs.pop('queryset', None)
        assert self.queryset is not None or kwargs.get('read_only', None), (
            'Relational field must provide a `queryset` argument, '
            'or set read_only=`True`.'
        )
        assert not (self.queryset is not None and kwargs.get('read_only', None)), (
            'Relational fields should not provide a `queryset` argument, '
            'when setting read_only=`True`.'
        )
        super(HyperlinkedRelatedModelSerializer, self).__init__(**kwargs)

    def run_validators(self, value):
        # No need to validate any fields except 'url' that is validated in to_internal_value method
        pass

    def to_internal_value(self, data):
        url_field = self.fields['url']

        # This is tricky: self.fields['url'] is the one generated
        # based on Meta.fields.
        # By default ModelSerializer generates it as HyperlinkedIdentityField,
        # which is read-only, thus it doesn't get deserialized from POST body.
        # So, we "borrow" its view_name and lookup_field to create
        # a HyperlinkedRelatedField which can turn url into a proper model
        # instance.
        url = serializers.HyperlinkedRelatedField(
            queryset=self.queryset.all(),
            view_name=url_field.view_name,
            lookup_field=url_field.lookup_field,
        )

        return url.to_internal_value(data['url'])
