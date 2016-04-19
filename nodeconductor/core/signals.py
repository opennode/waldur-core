import django.dispatch

# TODO: Make all the serializers emit this signal
pre_serializer_fields = django.dispatch.Signal(providing_args=['fields'])

post_validate_attrs = django.dispatch.Signal(providing_args=['attrs'])
