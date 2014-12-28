from __future__ import unicode_literals

from rest_framework import status
from rest_framework.exceptions import APIException


class ServiceUnavailableError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Service Unavailable.'


class IncorrectStateException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Cannot modify an object in its current state'
