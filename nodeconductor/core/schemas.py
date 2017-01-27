from rest_framework.permissions import AllowAny
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.schemas import SchemaGenerator, EndpointInspector
from rest_framework.views import APIView
from rest_framework_swagger import renderers


# XXX: Drop after removing HEAD requests
class WaldurEndpointInspector(EndpointInspector):
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


class WaldurSchemaGenerator(SchemaGenerator):
    endpoint_inspector_cls = WaldurEndpointInspector


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
