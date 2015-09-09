from django.db import models


class StructureQueryset(models.QuerySet):
    """ Provides additional filtering by customer (based on permission definition).

        Example:

            .. code-block:: python

                Droplet.objects.filter(
                    customer__name__startswith='A',
                    state=Droplet.States.ONLINE)

                Droplet.objects.filter(Q(customer__name='Alice') | Q(customer__name='Bob'))
    """

    def get(self, *args, **kwargs):
        return self.filter(*args, **kwargs).get()

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
            elif base_field == 'customer':
                args.update(self._filter_by_customer(field, val))
            else:
                args.update(**{field: val})

        return args

    def _filter_by_customer(self, field, customer):
        # handle 'customer' custom field
        # look for customer field path in Permissions class, fallback to FieldError if it's missed
        extra = '__'.join(field.split('__')[1:]) if '__' in field else None
        try:
            customer_path = self.model.Permissions.customer_path
        except AttributeError:
            return {field: customer}
        else:
            if customer_path == 'self':
                if extra:
                    return {extra: customer}
                else:
                    return {'pk': customer.pk if isinstance(customer, models.Model) else customer}
            else:
                if extra:
                    customer_path += '__' + extra
                return {customer_path: customer}


StructureManager = models.Manager.from_queryset(StructureQueryset)
