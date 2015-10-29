import logging

from django.contrib import auth
from django.db.models import ProtectedError
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import force_text

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import exception_handler as rf_exception_handler

from nodeconductor import __version__
from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.core.serializers import AuthTokenSerializer
from nodeconductor.logging.log import event_logger


logger = logging.getLogger(__name__)


class ObtainAuthToken(APIView):
    """
    Api view loosely based on DRF's default ObtainAuthToken,
    but with the responses formats and status codes aligned with BasicAuthentication behavior.
    """
    throttle_classes = ()
    permission_classes = ()
    serializer_class = AuthTokenSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']

        user = auth.authenticate(
            username=username,
            password=serializer.validated_data['password'],
        )

        if not user:
            logger.debug('Not returning auth token: '
                         'user %s does not exist', username)
            return Response(
                data={'detail': 'Invalid username/password'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            logger.debug('Not returning auth token: '
                         'user %s is disabled', username)
            return Response(
                data={'detail': 'User account is disabled'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        logger.debug('Returning token for successful login of user %s', user)
        event_logger.auth.info(
            'User {user_username} with full name {user_full_name} '
            'authenticated successfully with username and password.',
            event_type='auth_logged_in_with_username',
            event_context={'user': user})

        return Response({'token': token.key})


obtain_auth_token = ObtainAuthToken.as_view()


@api_view(['GET'])
@permission_classes((AllowAny, ))
def version_detail(request):
    """Retrieve version of the application"""

    return Response({'version': __version__})


# noinspection PyProtectedMember
def exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        dependent_meta = exc.protected_objects.model._meta

        try:
            # This exception should be raised from a viewset
            instance_meta = context['view'].get_queryset().model._meta
        except (AttributeError, KeyError):
            # Fallback, when instance being deleted cannot be inferred
            instance_name = 'object'
        else:
            instance_name = force_text(instance_meta.verbose_name)

        detail = 'Cannot delete {instance_name} with existing {dependant_objects}'.format(
            instance_name=instance_name,
            dependant_objects=force_text(dependent_meta.verbose_name_plural),
        )

        # We substitute exception here to get consistent representation
        # for both ProtectError and manually raised IncorrectStateException
        exc = IncorrectStateException(detail=detail)

    return rf_exception_handler(exc, context)
