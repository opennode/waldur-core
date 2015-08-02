from operator import itemgetter

from django.core.urlresolvers import NoReverseMatch
from django.utils.datastructures import SortedDict

from rest_framework import views
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.routers import DefaultRouter


class SortedDefaultRouter(DefaultRouter):

    def get_api_root_view(self):
        """
        Return a view to use as the API root.
        """
        api_root_dict = {}
        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        class APIRoot(views.APIView):
            _ignore_model_permissions = True

            def get(self, request, *args, **kwargs):
                ret = SortedDict()
                # sort items before inserting them into a dict
                for key, url_name in sorted(api_root_dict.items(), key=itemgetter(0)):
                    try:
                        ret[key] = reverse(
                            url_name,
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
