from rest_framework import filters as rf_filters
from rest_framework import mixins
from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure import models as structure_models
from nodeconductor.users import models, filters, serializers, tasks


class InvitationViewSet(mixins.CreateModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    queryset = models.Invitation.objects.all()
    serializer_class = serializers.InvitationSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    filter_backends = (
        structure_filters.GenericRoleFilter,
        rf_filters.DjangoFilterBackend,
        filters.InvitationCustomerFilterBackend,
    )
    filter_class = filters.InvitationFilter
    lookup_field = 'uuid'

    def can_manage_invitation_with(self, customer):
        user = self.request.user

        if user.is_staff:
            return True

        return customer.has_user(user, structure_models.CustomerRole.OWNER)

    def perform_create(self, serializer):
        project_role = serializer.validated_data.get('project_role', {})
        project = project_role.get('project')
        if project is not None:
            customer = project_role['project'].customer
        else:
            customer_role = serializer.validated_data.get('customer_role', {})
            customer = customer_role['customer']

        if not self.can_manage_invitation_with(customer):
            raise PermissionDenied('You do not have permission to perform this action.')

        invitation = serializer.save()
        tasks.send_invitation.delay(invitation.uuid.hex, self.request.user.full_name or self.request.user.username)

    @detail_route(methods=['post'])
    def send(self, request, uuid=None):
        invitation = self.get_object()

        if not self.can_manage_invitation_with(invitation.customer):
            raise PermissionDenied('You do not have permission to perform this action.')
        elif invitation.state != models.Invitation.State.PENDING:
            raise ValidationError('Only pending invitation can be resent.')

        tasks.send_invitation.delay(invitation.uuid.hex, self.request.user.full_name or self.request.user.username)
        return Response({'detail': "Invitation sending has been successfully scheduled."},
                        status=status.HTTP_200_OK)

    @detail_route(methods=['post'])
    def cancel(self, request, uuid=None):
        invitation = self.get_object()

        if not self.can_manage_invitation_with(invitation.customer):
            raise PermissionDenied('You do not have permission to perform this action.')
        elif invitation.state != models.Invitation.State.PENDING:
            raise ValidationError('Only pending invitation can be canceled.')

        invitation.cancel()
        return Response({'detail': "Invitation has been successfully canceled."},
                        status=status.HTTP_200_OK)

    @detail_route(methods=['post'], filter_backends=[], permission_classes=[permissions.IsAuthenticated])
    def accept(self, request, uuid=None):
        invitation = self.get_object()

        if invitation.state != models.Invitation.State.PENDING:
            raise ValidationError('Only pending invitation can be accepted.')
        elif invitation.civil_number and invitation.civil_number != request.user.civil_number:
            raise ValidationError('User has an invalid civil number.')

        invitation.accept(request.user)
        return Response({'detail': "Invitation has been successfully accepted."},
                        status=status.HTTP_200_OK)

    @detail_route(methods=['post'], filter_backends=[], permission_classes=[])
    def check(self, request, uuid=None):
        invitation = self.get_object()

        if invitation.state != models.Invitation.State.PENDING:
            return Response(status=status.HTTP_404_NOT_FOUND)
        elif invitation.civil_number:
            return Response({'civil_number_required': True}, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_200_OK)
