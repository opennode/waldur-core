from celery import Task as CeleryTask
from celery import current_app
from celery.app.task import _reprtask
from celery.five import with_metaclass
from celery.local import Proxy
from celery.utils.imports import gen_task_name

# This code copy from Celery 3 source.
# https://github.com/celery/celery/blob/3.1/celery/app/task.py


class _CompatShared(object):

    def __init__(self, name, cons):
        self.name = name
        self.cons = cons

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return '<OldTask: %r>' % (self.name, )

    def __call__(self, app):
        return self.cons(app)


class TaskType(type):
    """Meta class for tasks.

    Automatically registers the task in the task registry (except
    if the :attr:`Task.abstract`` attribute is set).

    If no :attr:`Task.name` attribute is provided, then the name is generated
    from the module and class name.

    """
    _creation_count = {}  # used by old non-abstract task classes

    def __new__(cls, name, bases, attrs):
        new = super(TaskType, cls).__new__
        task_module = attrs.get('__module__') or '__main__'

        # - Abstract class: abstract attribute should not be inherited.
        abstract = attrs.pop('abstract', None)
        if abstract or not attrs.get('autoregister', True):
            return new(cls, name, bases, attrs)

        # The 'app' attribute is now a property, with the real app located
        # in the '_app' attribute.  Previously this was a regular attribute,
        # so we should support classes defining it.
        app = attrs.pop('_app', None) or attrs.pop('app', None)

        # Attempt to inherit app from one the bases
        if not isinstance(app, Proxy) and app is None:
            for base in bases:
                if getattr(base, '_app', None):
                    app = base._app
                    break
            else:
                app = current_app._get_current_object()
        attrs['_app'] = app

        # - Automatically generate missing/empty name.
        task_name = attrs.get('name')
        if not task_name:
            attrs['name'] = task_name = gen_task_name(app, name, task_module)

        if not attrs.get('_decorated'):
            # non decorated tasks must also be shared in case
            # an app is created multiple times due to modules
            # imported under multiple names.
            # Hairy stuff,  here to be compatible with 2.x.
            # People should not use non-abstract task classes anymore,
            # use the task decorator.
            from celery._state import connect_on_app_finalize
            unique_name = '.'.join([task_module, name])
            if unique_name not in cls._creation_count:
                # the creation count is used as a safety
                # so that the same task is not added recursively
                # to the set of constructors.
                cls._creation_count[unique_name] = 1
                connect_on_app_finalize(_CompatShared(
                    unique_name,
                    lambda app: TaskType.__new__(cls, name, bases,
                                                 dict(attrs, _app=app)),
                ))

        # - Create and register class.
        # Because of the way import happens (recursively)
        # we may or may not be the first time the task tries to register
        # with the framework.  There should only be one class for each task
        # name, so we always return the registered version.
        tasks = app._tasks
        if task_name not in tasks:
            tasks.register(new(cls, name, bases, attrs))
        instance = tasks[task_name]
        instance.bind(app)
        return instance.__class__

    def __repr__(cls):
        return _reprtask(cls)


@with_metaclass(TaskType)
class CeleryTaskWithAutoRegister(CeleryTask):
    """ This class is needed for update Celery from 3 to 4 version.
    Because 'The Task class is no longer using a special meta-class that automatically
    registers the task in the task registry.'
    http://docs.celeryproject.org/en/latest/whatsnew-4.0.html#the-task-base-class-no-longer-automatically-register-tasks
    """
    pass
