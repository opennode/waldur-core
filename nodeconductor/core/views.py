from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from nodeconductor.core.serializers import AuthTokenSerializer


class ObtainAuthToken(APIView):
    """
    Api view loosely based on DRF's default ObtainAuthToken,
    but with the responses formats and status codes aligned with BasicAuthentication behavior.
    """
    throttle_classes = ()
    permission_classes = ()
    serializer_class = AuthTokenSerializer
    model = Token

    def post(self, request):
        serializer = self.serializer_class(data=request.DATA)
        if serializer.is_valid():
            token, created = Token.objects.get_or_create(user=serializer.object['user'])
            return Response({'token': token.key})

        errors = dict(serializer.errors)

        try:
            non_field_errors = errors.pop('non_field_errors')
            errors['detail'] = non_field_errors[0]
        except (KeyError, IndexError):
            pass

        return Response(errors, status=status.HTTP_401_UNAUTHORIZED)


obtain_auth_token = ObtainAuthToken.as_view()
