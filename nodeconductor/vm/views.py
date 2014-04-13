from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from nodeconductor.vm.serializers import VmSerializer


class VmList(APIView):
    def post(self, request, format=None):
        '''
        Provisions a vm
        '''
        # This is a stub so far
        vms = [
            dict(
                name='name_{0}'.format(i),
                image='image_{0}'.format(i),
                volume_size=i,
            ) for i in xrange(10)
        ]

        serializer = VmSerializer(data=request.DATA)
        if serializer.is_valid():
            vms.append(serializer.object)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
