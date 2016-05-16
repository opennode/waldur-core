from rest_framework import exceptions, status


class CostLimitExceeded(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
