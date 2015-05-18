from __future__ import unicode_literals

import nodeconductor.events.middleware

import rest_framework.authentication


def user_capturing_auth(auth):
    class CapturingAuthentication(auth):
        def authenticate(self, request):
            result = super(CapturingAuthentication, self).authenticate(request)
            if result is not None:
                user, _ = result
                nodeconductor.events.middleware.set_current_user(user)
            return result

    return CapturingAuthentication


SessionAuthentication = user_capturing_auth(rest_framework.authentication.SessionAuthentication)
TokenAuthentication = user_capturing_auth(rest_framework.authentication.TokenAuthentication)
