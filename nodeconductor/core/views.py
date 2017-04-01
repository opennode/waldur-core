import logging

from django.contrib import auth
from django.core.cache import cache
from django.db.models import ProtectedError
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _

from rest_framework import status, mixins as rf_mixins, viewsets, permissions as rf_permissions, exceptions
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import exception_handler as rf_exception_handler

from nodeconductor import __version__
from nodeconductor.core import mixins, permissions
from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.core.serializers import AuthTokenSerializer
from nodeconductor.logging.loggers import event_logger


logger = logging.getLogger(__name__)


class RefreshTokenMixin(object):
    """
    This mixin is used in both password and social auth (implemented via plugin).
    Mixin allows to create new token if it does not exist yet or if it has already expired.
    Token is refreshed if it has not expired yet.
    """
    def refresh_token(self, user):
        token, created = Token.objects.get_or_create(user=user)

        if user.token_lifetime:
            lifetime = timezone.timedelta(seconds=user.token_lifetime)

            if token.created < timezone.now() - lifetime:
                token.delete()
                token = Token.objects.create(user=user)
                created = True

        if not created:
            token.created = timezone.now()
            token.save(update_fields=['created'])

        return token


class ObtainAuthToken(RefreshTokenMixin, APIView):
    """
    Api view loosely based on DRF's default ObtainAuthToken,
    but with the responses formats and status codes aligned with BasicAuthentication behavior.

    Valid request example:

    .. code-block:: http

        POST /api-auth/password/ HTTP/1.1
        Accept: application/json
        Content-Type: application/json
        Host: example.com

        {
            "username": "alice",
            "password": "$ecr3t"
        }

    Success response example:

    .. code-block:: http

        HTTP/1.0 200 OK
        Allow: POST, OPTIONS
        Content-Type: application/json
        Vary: Accept, Cookie

        {
            "token": "c84d653b9ec92c6cbac41c706593e66f567a7fa4"
        }

    Field validation failure response example:

    .. code-block:: http

        HTTP/1.0 401 UNAUTHORIZED
        Allow: POST, OPTIONS
        Content-Type: application/json

        {
            "password": ["This field is required."]
        }

    Invalid credentials failure response example:

    .. code-block:: http

        HTTP/1.0 401 UNAUTHORIZED
        Allow: POST, OPTIONS
        Content-Type: application/json

        {
            "detail": "Invalid username/password"
        }
    """
    throttle_classes = ()
    permission_classes = ()
    serializer_class = AuthTokenSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']

        source_ip = request.META.get('REMOTE_ADDR')
        auth_failure_key = 'LOGIN_FAILURES_OF_%s_AT_%s' % (username, source_ip)
        auth_failures = cache.get(auth_failure_key) or 0
        lockout_time_in_mins = 10

        if auth_failures >= 4:
            logger.debug('Not returning auth token: '
                         'username %s from %s is locked out' % (username, source_ip))
            return Response(
                data={'detail': _('Username is locked out. Try in %s minutes.') % lockout_time_in_mins},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = auth.authenticate(
            username=username,
            password=serializer.validated_data['password'],
        )

        if not user:
            logger.debug('Not returning auth token: '
                         'user %s does not exist', username)
            cache.set(auth_failure_key, auth_failures + 1, lockout_time_in_mins * 60)
            event_logger.auth.info(
                'User {username} failed to authenticate with username and password.',
                event_type='auth_login_failed_with_username',
                event_context={'username': username})

            return Response(
                data={'detail': _('Invalid username/password.')},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        else:
            cache.delete(auth_failure_key)

        if not user.is_active:
            logger.debug('Not returning auth token: '
                         'user %s is disabled', username)
            return Response(
                data={'detail': _('User account is disabled.')},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = self.refresh_token(user)

        logger.debug('Returning token for successful login of user %s', user)
        event_logger.auth.info(
            'User {user_username} with full name {user_full_name} '
            'authenticated successfully with username and password.',
            event_type='auth_logged_in_with_username',
            event_context={'user': user})

        return Response({'token': token.key})


obtain_auth_token = ObtainAuthToken.as_view()


@api_view(['GET'])
@permission_classes((rf_permissions.AllowAny, ))
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

        detail = _('Cannot delete {instance_name} with existing {dependant_objects}').format(
            instance_name=instance_name,
            dependant_objects=force_text(dependent_meta.verbose_name_plural),
        )

        # We substitute exception here to get consistent representation
        # for both ProtectError and manually raised IncorrectStateException
        exc = IncorrectStateException(detail=detail)

    return rf_exception_handler(exc, context)


class StateExecutorViewSet(mixins.StateMixin,
                           mixins.CreateExecutorMixin,
                           mixins.UpdateExecutorMixin,
                           mixins.DeleteExecutorMixin,
                           viewsets.ModelViewSet):
    """ Create/Update/Delete operations via executors """
    pass


class UpdateOnlyViewSet(rf_mixins.RetrieveModelMixin,
                        rf_mixins.UpdateModelMixin,
                        rf_mixins.DestroyModelMixin,
                        rf_mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    """ All default operations except create """
    pass


class UpdateOnlyStateExecutorViewSet(mixins.StateMixin,
                                     mixins.UpdateExecutorMixin,
                                     mixins.DeleteExecutorMixin,
                                     UpdateOnlyViewSet):
    """ Update/Delete operations via executors """
    pass


class ProtectedViewSet(rf_mixins.CreateModelMixin,
                       rf_mixins.RetrieveModelMixin,
                       rf_mixins.ListModelMixin,
                       viewsets.GenericViewSet):
    """ All default operations except update and delete """
    pass


class ActionsViewSet(viewsets.ModelViewSet):
    """
    Treats all endpoint actions in the same way.

    1. Allow to define separate serializers for each action:

        def action(self, request, *args, **kwargs):
            serializer = self.get_serializer(...)
            ...

        action_serializer_class = ActionSerializer

    2. Allow to define validators for detail actions:

        def state_is_ok(obj):
            if obj.state != 'ok':
                raise IncorrectStateException('Instance should be in state OK.')

        @decorators.detail_route()
        def action(self, request, *args, **kwargs):
            ...

        action_validators = [state_is_ok]

    3. Allow to define permissions checks for all actions or each action
       separately. Check ActionPermissionsBackend for more details.

    4. To avoid dancing around mixins - allow disabling actions:

        class MyView(ActionsViewSet):
            disabled_actions = ['create']  # error 405 will be returned on POST request
    """
    disabled_actions = []
    permission_classes = (rf_permissions.IsAuthenticated, permissions.ActionsPermission)

    def get_serializer_class(self):
        default_serializer_class = super(ActionsViewSet, self).get_serializer_class()
        if self.action is None:
            return default_serializer_class
        return getattr(self, self.action + '_serializer_class', default_serializer_class)

    def initial(self, request, *args, **kwargs):
        super(ActionsViewSet, self).initial(request, *args, **kwargs)
        if self.action is None:  # disable all checks if user tries to reach unsupported action
            return
        # check if action is allowed
        if self.action in getattr(self, 'disabled_actions', []):
            raise exceptions.MethodNotAllowed(method=request.method)
        if self.action != 'metadata':
            self.validate_object_action(self.action)

    def validate_object_action(self, action_name, obj=None):
        """ Execute validation for actions that are related to particular object """
        action_method = getattr(self, action_name)
        if not getattr(action_method, 'detail', False) and action_name not in ('update', 'partial_update', 'destroy'):
            # DRF does not add flag 'detail' to update and delete actions, however they execute operation with
            # particular object. We need to enable validation for them too.
            return
        validators = getattr(self, action_name + '_validators', [])
        for validator in validators:
            validator(obj or self.get_object())


class ReadOnlyActionsViewSet(ActionsViewSet):
    disabled_actions = ['create', 'update', 'partial_update', 'destroy']
