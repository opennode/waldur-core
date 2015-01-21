from __future__ import unicode_literals

from collections import OrderedDict

from django.core.paginator import EmptyPage
from django.db.models import ProtectedError
from django.utils.encoding import force_text

from rest_framework import status
from rest_framework.response import Response
from rest_framework.templatetags.rest_framework import replace_query_param

from nodeconductor.core.exceptions import IncorrectStateException


class DestroyModelMixin(object):
    """
    Destroy a model instance.
    """

    # noinspection PyProtectedMember
    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()

        try:
            self.pre_delete(obj)
            obj.delete()
            self.post_delete(obj)
        except ProtectedError as e:
            instance_meta = obj._meta
            dependent_meta = e.protected_objects.model._meta

            detail = 'Cannot delete {instance} with existing {dependant_objects}'.format(
                instance=force_text(instance_meta.verbose_name),
                dependant_objects=force_text(dependent_meta.verbose_name_plural),
            )
            raise IncorrectStateException(detail=detail)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ListModelMixin(object):
    """
    List a queryset.

    Paginates result without modifying the format of the response.
    Instead headers are used for pagination info.
    """
    page_field = 'page'
    _siblings = OrderedDict((
        ('first', lambda p: p.paginator.page_range[0]),
        ('prev', lambda p: p.previous_page_number()),
        ('next', lambda p: p.next_page_number()),
        ('last', lambda p: p.paginator.page_range[-1]),
    ))

    def list(self, request, *args, **kwargs):
        instance = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(instance)
        serializer = self.get_serializer(page, many=True)
        headers = self.get_pagination_headers(request, page)

        return Response(serializer.data, headers=headers)

    def get_pagination_headers(self, request, page):
        if page is None:
            return {}

        links = []
        url = request and request.build_absolute_uri() or ''

        for rel, get_page_number in self._siblings.items():
            try:
                page_url = replace_query_param(url, self.page_field, get_page_number(page))
                links.append('<%s>; rel="%s"' % (page_url, rel))
            except EmptyPage:
                pass

        headers = {
            'X-Result-Count': page.paginator.count,
        }

        if links:
            headers['Link'] = ', '.join(links)

        return headers
