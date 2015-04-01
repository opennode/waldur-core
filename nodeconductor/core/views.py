import logging

from django.contrib import auth
from django.db.models import ProtectedError
from django.views.decorators.csrf import csrf_exempt
from django.utils.encoding import force_text

from djangosaml2.conf import get_config
from djangosaml2.signals import post_authenticated
from djangosaml2.utils import get_custom_setting
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import exception_handler as rf_exception_handler
from saml2.client import Saml2Client

from nodeconductor import __version__
from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.core.serializers import AuthTokenSerializer, Saml2ResponseSerializer


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


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
        event_logger.info(
            "User '%s' with full name '%s' authenticated successfully with username and password",
            user.username, user.full_name,
            extra={'user': user, 'event_type': 'auth_logged_in_with_username'})
        logger.debug('Returning token for successful login of user %s', user)
        return Response({'token': token.key})


obtain_auth_token = ObtainAuthToken.as_view()


class Saml2AuthView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = Saml2ResponseSerializer

    @csrf_exempt
    def post(self, request):
        """SAML Authorization Response endpoint

        The IdP will send its response to this view, which
        will process it with pysaml2 help and log the user
        in using the custom Authorization backend
        djangosaml2.backends.Saml2Backend that should be
        enabled in the settings.py
        """
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            errors = dict(serializer.errors)

            try:
                non_field_errors = errors.pop('non_field_errors')
                errors['detail'] = non_field_errors[0]
            except (KeyError, IndexError):
                pass

            return Response(errors, status=status.HTTP_401_UNAUTHORIZED)

        attribute_mapping = get_custom_setting(
            'SAML_ATTRIBUTE_MAPPING', {'uid': ('username', )})
        create_unknown_user = get_custom_setting(
            'SAML_CREATE_UNKNOWN_USER', True)

        conf = get_config(request=request)
        client = Saml2Client(conf, logger=logger)

        post = {'SAMLResponse': serializer.object['saml2response']}

        # process the authentication response
        # noinspection PyBroadException
        try:
            response = client.response(
                post,
                outstanding=None,  # Rely on allow_unsolicited setting
                decode=False,      # The response is already base64 decoded
            )
        except Exception as e:
            logger.error('SAML response parsing failed %s' % e)
            response = None

        if response is None:
            return Response(
                {'saml2response': 'SAML2 response has errors.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # authenticate the remote user
        session_info = response.session_info()

        user = auth.authenticate(
            session_info=session_info,
            attribute_mapping=attribute_mapping,
            create_unknown_user=create_unknown_user,
        )
        if user is None:
            logger.info('Authentication with SAML token has failed, user not found')
            return Response(
                {'detail': 'SAML2 authentication failed'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        post_authenticated.send_robust(sender=user, session_info=session_info)

        token, _ = Token.objects.get_or_create(user=user)
        event_logger.info(
            "User '%s' with full name '%s' authenticated successfully with Omani PKI",
            user.username, user.full_name,
            extra={'user': user, 'event_type': 'auth_logged_in_with_pki'})
        logger.info('Authenticated with SAML token. Returning token for successful login of user %s', user)
        return Response({'token': token.key})

assertion_consumer_service = Saml2AuthView.as_view()


@api_view(['GET'])
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
