from collections import OrderedDict
from operator import itemgetter

from django.core.urlresolvers import NoReverseMatch

from rest_framework import views, exceptions
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import SchemaGenerator


class SortedDefaultRouter(DefaultRouter):

    def get_api_root_view(self, api_urls=None):
        """
        Return a view to use as the API root.
        """
        api_root_dict = OrderedDict()
        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        view_renderers = list(self.root_renderers)
        schema_media_types = []

        if api_urls and self.schema_title:
            view_renderers += list(self.schema_renderers)
            schema_generator = SchemaGenerator(
                title=self.schema_title,
                url=self.schema_url,
                patterns=api_urls
            )
            schema_media_types = [
                renderer.media_type
                for renderer in self.schema_renderers
            ]

        class APIRoot(views.APIView):
            _ignore_model_permissions = True
            renderer_classes = view_renderers

            def get(self, request, *args, **kwargs):
                if request.accepted_renderer.media_type in schema_media_types:
                    # Return a schema response.
                    schema = schema_generator.get_schema(request)
                    if schema is None:
                        raise exceptions.PermissionDenied()
                    return Response(schema)

                # Return a plain {"name": "hyperlink"} response.
                ret = OrderedDict()
                namespace = request.resolver_match.namespace
                for key, url_name in sorted(api_root_dict.items(), key=itemgetter(0)):
                    if namespace:
                        url_name = namespace + ':' + url_name
                    try:
                        ret[key] = reverse(
                            url_name,
                            args=args,
                            kwargs=kwargs,
                            request=request,
                            format=kwargs.get('format', None)
                        )
                    except NoReverseMatch:
                        # Don't bail out if eg. no list routes exist, only detail routes.
                        continue

                return Response(ret)

        return APIRoot.as_view()

    def get_default_base_name(self, viewset):
        """
        Attempt to automatically determine base name using `get_url_name`.
        """
        queryset = getattr(viewset, 'queryset', None)

        if queryset is not None:
            get_url_name = getattr(queryset.model, 'get_url_name', None)
            if get_url_name is not None:
                return get_url_name()

        return super(SortedDefaultRouter, self).get_default_base_name(viewset)
