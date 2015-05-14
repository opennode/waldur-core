
from django.db import models
from django.core.exceptions import ImproperlyConfigured
from polymorphic.base import PolymorphicModelBase


class ServiceWithProjectsBase(PolymorphicModelBase):
    def __new__(cls, name, bases, attrs):
        model = super(ServiceWithProjectsBase, cls).__new__(cls, name, bases, attrs)
        field = 'projects'

        if hasattr(model, field) and getattr(model, field) is NotImplemented:
            delattr(model, field)

        if any(True for b in bases if b.__name__ == 'Service'):
            field_val = attrs.get(field)
            if isinstance(field_val, models.ManyToManyField):
                pass
            elif isinstance(field_val, basestring):
                model.add_to_class(field, models.ManyToManyField(
                    'structure.Project', related_name='services', through=field_val))
            else:
                raise ImproperlyConfigured(
                    "'%s' field of %s must be defined as "
                    "a class name of an actual ServiceProjectLink" % (field, name))

        return model


class ServiceBackReferenceBase(models.base.ModelBase):
    def __new__(cls, name, bases, attrs):
        model = super(ServiceBackReferenceBase, cls).__new__(cls, name, bases, attrs)
        field = 'service'
        classes = 'ServiceResource', 'ServiceProjectLink'

        if hasattr(model, field) and getattr(model, field) is NotImplemented:
            delattr(model, field)

        if any(True for b in bases if b.__name__ in classes):
            field_val = attrs.get(field)
            if isinstance(field_val, models.ForeignKey):
                pass
            elif isinstance(field_val, basestring) or (
                    isinstance(field_val, type) and issubclass(field_val, models.Model)):
                model.add_to_class(field, models.ForeignKey(field_val))
            else:
                raise ImproperlyConfigured(
                    "'%s' field of %s must be defined as "
                    "a class of an actual Service" % (field, name))

        return model
