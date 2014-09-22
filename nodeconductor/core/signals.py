import django.dispatch

# TODO: Make all the serializers emit this signal
pre_serializer_fields = django.dispatch.Signal(providing_args=['fields'])
