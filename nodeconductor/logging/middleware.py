from __future__ import unicode_literals

import threading

_locals = threading.local()


def get_context():
    return getattr(_locals, 'context', None)


def set_context(context):
    _locals.context = context


def reset_context():
    if hasattr(_locals, 'context'):
        del _locals.context


def get_ip_address(request):
    """
    Correct IP address is expected as first element of HTTP_X_FORWARDED_FOR or REMOTE_ADDR 
    """
    if 'HTTP_X_FORWARDED_FOR' in request.META:
        return request.META['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    else:
        return request.META['REMOTE_ADDR']


class CaptureEventContextMiddleware(object):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user.is_anonymous():
            reset_log_context()
            return

        context = user._get_log_context('user')
        context['ip_address'] = get_ip_address(request)
        set_log_context(context)

    def process_response(self, request, response):
        reset_current_context()
        return response
