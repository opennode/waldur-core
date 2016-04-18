from __future__ import unicode_literals

from rest_framework import status
from rest_framework.exceptions import APIException


class QuotaError(Exception):
    pass


class CreationConditionFailedQuotaError(QuotaError):
    pass


class QuotaExceededException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'One or more quotas are over limit'


class BackendQuotaUpdateError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'It is impossible to modify backend quota through this endpoint.',
