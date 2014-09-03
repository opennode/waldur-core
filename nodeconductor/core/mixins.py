from __future__ import unicode_literals
from rest_framework.templatetags.rest_framework import replace_query_param
import warnings

from django.core.exceptions import ValidationError
from django.http.response import Http404

from rest_framework import status
from rest_framework.mixins import _get_validation_exclusions
from rest_framework.response import Response


class UpdateOnlyModelMixin(object):
    """
    Update a model instance.

    This mixin forbids creation of resources via PUT.
    """
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        self.object = self.get_object()

        serializer = self.get_serializer(self.object, data=request.DATA,
                                         files=request.FILES, partial=partial)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            self.pre_save(serializer.object)
        except ValidationError as err:
            # full_clean on model instance may be called in pre_save,
            # so we have to handle eventual errors.
            return Response(err.message_dict, status=status.HTTP_400_BAD_REQUEST)

        self.object = serializer.save(force_update=True)
        self.post_save(self.object, created=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def pre_save(self, obj):
        """
        Set any attributes on the object that are implicit in the request.
        """
        # pk and/or slug attributes are implicit in the URL.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup = self.kwargs.get(lookup_url_kwarg, None)
        pk = self.kwargs.get(self.pk_url_kwarg, None)
        slug = self.kwargs.get(self.slug_url_kwarg, None)
        slug_field = slug and self.slug_field or None

        if lookup:
            setattr(obj, self.lookup_field, lookup)

        if pk:
            setattr(obj, 'pk', pk)

        if slug:
            setattr(obj, slug_field, slug)

        # Ensure we clean the attributes so that we don't eg return integer
        # pk using a string representation, as provided by the url conf kwarg.
        if hasattr(obj, 'full_clean'):
            exclude = _get_validation_exclusions(obj, pk, slug_field, self.lookup_field)
            obj.full_clean(exclude)


class ListModelMixin(object):
    """
    List a queryset.
    """
    empty_error = "Empty list and '%(class_name)s.allow_empty' is False."
    page_field = 'page'

    def list(self, request, *args, **kwargs):
        self.object_list = self.filter_queryset(self.get_queryset())

        # Default is to allow empty querysets.  This can be altered by setting
        # `.allow_empty = False`, to raise 404 errors on empty querysets.
        if not self.allow_empty and not self.object_list:
            warnings.warn(
                'The `allow_empty` parameter is due to be deprecated. '
                'To use `allow_empty=False` style behavior, You should override '
                '`get_queryset()` and explicitly raise a 404 on empty querysets.',
                PendingDeprecationWarning
            )
            class_name = self.__class__.__name__
            error_msg = self.empty_error % {'class_name': class_name}
            raise Http404(error_msg)

        page = self.paginate_queryset(self.object_list)
        headers = {}
        if page is not None:
            headers = self.get_pagination_headers(request, page)

        serializer = self.get_serializer(page, many=True)

        return Response(serializer.data, headers=headers)

    def _get_next_page_url(self, request, value):
        if not value.has_next():
            return None
        page = value.next_page_number()
        url = request and request.build_absolute_uri() or ''
        return replace_query_param(url, self.page_field, page)

    def _get_previous_page_url(self, request, value):
        if not value.has_previous():
            return None
        page = value.previous_page_number()
        url = request and request.build_absolute_uri() or ''
        return replace_query_param(url, self.page_field, page)

    def get_pagination_headers(self, request, page):
        try:
            next = self._get_next_page_url(request, page)
            previous = self._get_previous_page_url(request, page)

            return {'Count': page.paginator.count,
                    'Next': next,
                    'Previous': previous}
        except (TypeError, KeyError):
            return {}
