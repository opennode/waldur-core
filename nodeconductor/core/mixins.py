from __future__ import unicode_literals

from collections import OrderedDict

from django.core.paginator import EmptyPage
from django.db.models import ProtectedError
from django.utils.encoding import force_text

from rest_framework import status
from rest_framework.response import Response
from rest_framework.templatetags.rest_framework import replace_query_param

from nodeconductor.core.models import SynchronizableMixin, SynchronizationStates
from nodeconductor.core.exceptions import IncorrectStateException


class DestroyModelMixin(object):
    """
    Destroy a model instance.
    """

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        try:
            self.perform_destroy(instance)
        except ProtectedError as e:
            instance_meta = instance._meta
            dependent_meta = e.protected_objects.model._meta

            detail = 'Cannot delete {instance} with existing {dependant_objects}'.format(
                instance=force_text(instance_meta.verbose_name),
                dependant_objects=force_text(dependent_meta.verbose_name_plural),
            )
            raise IncorrectStateException(detail=detail)

        return Response(status=status.HTTP_204_NO_CONTENT)

    # noinspection PyMethodMayBeStatic
    def perform_destroy(self, instance):
        instance.delete()


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
        if self.paginate_by is not None:
            page = self.paginate_queryset(instance)
            serializer = self.get_serializer(page, many=True)
            headers = self.get_pagination_headers(request, page)
        else:
            serializer = self.get_serializer(instance, many=True)
            headers = {}

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


class UpdateOnlyStableMixin(object):
    """
    Allow modification of entities in stable state only.
    """

    def initial(self, request, *args, **kwargs):
        if self.action in ('update', 'partial_update', 'destroy'):
            obj = self.get_object()
            if obj and isinstance(obj, SynchronizableMixin):
                if obj.state not in SynchronizationStates.STABLE_STATES:
                    raise IncorrectStateException(
                        'Modification allowed in stable states only.')

        return super(UpdateOnlyStableMixin, self).initial(request, *args, **kwargs)
