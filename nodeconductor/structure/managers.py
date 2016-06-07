import copy
import functools
import itertools
import heapq
from operator import or_

from django.db import models

from nodeconductor.core.managers import GenericKeyMixin


def filter_queryset_for_user(queryset, user):
    filtered_relations = ('customer', 'project', 'project_group')

    if user is None or user.is_staff:
        return queryset

    def create_q(entity):
        try:
            path = getattr(permissions, '%s_path' % entity)
        except AttributeError:
            return None

        role = getattr(permissions, '%s_role' % entity, None)

        if path == 'self':
            prefix = ''
        else:
            prefix = path + '__'

        kwargs = {
            prefix + 'roles__permission_group__user': user,
        }

        if role:
            kwargs[prefix + 'roles__role_type'] = role

        return models.Q(**kwargs)

    try:
        permissions = queryset.model.Permissions
    except AttributeError:
        return queryset

    q_objects = [q_object for q_object in (
        create_q(entity) for entity in filtered_relations
    ) if q_object is not None]

    try:
        # Add extra query which basically allows to
        # additionally filter by some flag and ignore permissions
        extra_q = getattr(permissions, 'extra_query')
    except AttributeError:
        pass
    else:
        q_objects.append(models.Q(**extra_q))

    try:
        # Whether both customer and project filtering requested?
        any_of_q = reduce(or_, q_objects)
        return queryset.filter(any_of_q).distinct()
    except TypeError:
        # Or any of customer and project filtering requested?
        return queryset.filter(q_objects[0])
    except IndexError:
        # Looks like no filters are there
        return queryset


class StructureQueryset(models.QuerySet):
    """ Provides additional filtering by customer or project (based on permission definition).

        Example:

            .. code-block:: python

                Instance.objects.filter(project=12)

                Droplet.objects.filter(
                    customer__name__startswith='A',
                    state=Droplet.States.ONLINE)

                Droplet.objects.filter(Q(customer__name='Alice') | Q(customer__name='Bob'))
    """

    def exclude(self, *args, **kwargs):
        return super(StructureQueryset, self).exclude(
            *[self._patch_query_argument(a) for a in args],
            **self._filter_by_custom_fields(**kwargs))

    def filter(self, *args, **kwargs):
        return super(StructureQueryset, self).filter(
            *[self._patch_query_argument(a) for a in args],
            **self._filter_by_custom_fields(**kwargs))

    def _patch_query_argument(self, arg):
        # patch Q() objects if passed and add support of custom fields
        if isinstance(arg, models.Q):
            children = []
            for opt in arg.children:
                if isinstance(opt, models.Q):
                    children.append(self._patch_query_argument(opt))
                else:
                    args = self._filter_by_custom_fields(**dict([opt]))
                    children.append(tuple(args.items())[0])
            arg.children = children
        return arg

    def _filter_by_custom_fields(self, **kwargs):
        # traverse over filter arguments in search of custom fields
        args = {}
        fields = self.model._meta.get_all_field_names()
        for field, val in kwargs.items():
            base_field = field.split('__')[0]
            if base_field in fields:
                args.update(**{field: val})
            elif base_field in ('customer', 'project'):
                args.update(self._filter_by_permission_fields(base_field, field, val))
            else:
                args.update(**{field: val})

        return args

    def _filter_by_permission_fields(self, name, field, value):
        # handle fields connected via permissions relations
        extra = '__'.join(field.split('__')[1:]) if '__' in field else None
        try:
            # look for the target field path in Permissions class,
            path = getattr(self.model.Permissions, '%s_path' % name)
        except AttributeError:
            # fallback to FieldError if it's missed
            return {field: value}
        else:
            if path == 'self':
                if extra:
                    return {extra: value}
                else:
                    return {'pk': value.pk if isinstance(value, models.Model) else value}
            else:
                if extra:
                    path += '__' + extra
                return {path: value}


StructureManager = models.Manager.from_queryset(StructureQueryset)


class SummaryQuerySet(object):
    """ Fake queryset that emulates union of different models querysets """

    def __init__(self, summary_models):
        self.querysets = [model.objects.all() for model in summary_models]
        self._order_by = None

    def filter(self, *args, **kwargs):
        self.querysets = [qs.filter(*copy.deepcopy(args), **copy.deepcopy(kwargs)) for qs in self.querysets]
        return self

    def distinct(self, *args, **kwargs):
        self.querysets = [qs.distinct(*copy.deepcopy(args), **copy.deepcopy(kwargs)) for qs in self.querysets]
        return self

    def order_by(self, order_by):
        self._order_by = order_by
        self.querysets = [qs.order_by(copy.deepcopy(order_by)) for qs in self.querysets]
        return self

    def all(self):
        return self

    def none(self):
        try:
            return self.querysets[0].none()
        except IndexError:
            return

    def __getitem__(self, val):
        chained_querysets = self._get_chained_querysets()
        if isinstance(val, slice):
            return list(itertools.islice(chained_querysets, val.start, val.stop))
        else:
            try:
                return itertools.islice(chained_querysets, val, val + 1).next()
            except StopIteration:
                raise IndexError

    def __len__(self):
        return sum([q.count() for q in self.querysets])

    def _get_chained_querysets(self):
        if self._order_by:
            return self._merge([qs.iterator() for qs in self.querysets], compared_attr=self._order_by)
        else:
            return itertools.chain(*[qs.iterator() for qs in self.querysets])

    def _merge(self, subsequences, compared_attr='pk'):

        @functools.total_ordering
        class Compared(object):
            """ Order objects by their attributes, reverse ordering if <reverse> is True """
            def __init__(self, obj, attr, reverse=False):
                self.attr = reduce(Compared.get_obj_attr, attr.split("__"), obj)
                if isinstance(self.attr, basestring):
                    self.attr = self.attr.lower()
                self.reverse = reverse

            @staticmethod
            def get_obj_attr(obj, attr):
                # for m2m relationship support - get first instance of manager.
                # for example: get first project group if resource has to be ordered by project groups.
                if isinstance(obj, models.Manager):
                    obj = obj.first()
                return getattr(obj, attr) if obj else None

            def __eq__(self, other):
                return self.attr == other.attr

            def __le__(self, other):
                # In MySQL NULL values come *first* with ascending sort order.
                # We use the same behaviour.
                if self.attr is None:
                    return not self.reverse
                elif other.attr is None:
                    return self.reverse
                else:
                    return self.attr < other.attr if not self.reverse else self.attr >= other.attr

        reverse = compared_attr.startswith('-')
        if reverse:
            compared_attr = compared_attr[1:]

        # prepare a heap whose items are
        # (compared, current-value, iterator), one each per (non-empty) subsequence
        # <compared> is used for model instances comparison based on given attribute
        heap = []
        for subseq in subsequences:
            iterator = iter(subseq)
            for current_value in iterator:
                # subseq is not empty, therefore add this subseq's item to the list
                heapq.heappush(
                    heap, (Compared(current_value, compared_attr, reverse=reverse), current_value, iterator))
                break

        while heap:
            # get and yield lowest current value (and corresponding iterator)
            _, current_value, iterator = heap[0]
            yield current_value
            for current_value in iterator:
                # subseq is not finished, therefore add this subseq's item back into the priority queue
                heapq.heapreplace(
                    heap, (Compared(current_value, compared_attr, reverse=reverse), current_value, iterator))
                break
            else:
                # subseq has been exhausted, therefore remove it from the queue
                heapq.heappop(heap)


class ResourceSummaryQuertSet(SummaryQuerySet):
    # Hack for permissions
    @property
    def model(self):
        from nodeconductor.structure.models import ResourceMixin
        return ResourceMixin


class ServiceSummaryQuerySet(SummaryQuerySet):
    # Hack for permissions
    @property
    def model(self):
        from nodeconductor.structure.models import Service
        return Service


class ServiceSettingsManager(GenericKeyMixin, models.Manager):
    """ Allows to filter and get service settings by generic key """

    def get_available_models(self):
        """ Return list of models that are acceptable """
        from nodeconductor.structure.models import ResourceMixin
        return ResourceMixin.get_all_models()
