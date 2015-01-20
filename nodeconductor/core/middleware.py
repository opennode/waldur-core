from __future__ import unicode_literals

import threading

_locals = threading.local()


def get_current_user():
    return getattr(_locals, 'user', None)


def set_current_user(user):
    if user is None or user.is_anonymous():
        reset_current_user()
    else:
        _locals.user = user


def reset_current_user():
    try:
        del _locals.user
    except AttributeError:
        pass


# noinspection PyMethodMayBeStatic
class CaptureUserMiddleware(object):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        set_current_user(user)

    def process_response(self, request, response):
        reset_current_user()
        return response
