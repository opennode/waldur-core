import collections

from django.contrib.auth import get_user_model
import requests
from rest_framework.exceptions import PermissionDenied

from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.core.models import SshPublicKey


Coordinates = collections.namedtuple('Coordinates', ('latitude', 'longitude'))


class GeoIpException(Exception):
    pass


def serialize_ssh_key(ssh_key):
    return {
        'name': ssh_key.name,
        'user_id': ssh_key.user_id,
        'fingerprint': ssh_key.fingerprint,
        'public_key': ssh_key.public_key,
        'uuid': ssh_key.uuid.hex
    }


def deserialize_ssh_key(data):
    return SshPublicKey(
        name=data['name'],
        user_id=data['user_id'],
        fingerprint=data['fingerprint'],
        public_key=data['public_key'],
        uuid=data['uuid']
    )


def serialize_user(user):
    return {
        'username': user.username,
        'email': user.email
    }


def deserialize_user(data):
    return get_user_model()(
        username=data['username'],
        email=data['email']
    )


def get_coordinates_by_ip(ip_address):
    url = 'http://freegeoip.net/json/{}'.format(ip_address)

    response = requests.get(url)
    if response.ok:
        data = response.json()
        return Coordinates(latitude=data['latitude'],
                           longitude=data['longitude'])
    else:
        params = (url, response.status_code, response.text)
        raise GeoIpException("Request to geoip API %s failed: %s %s" % params)


def check_operation(user, resource, operation_name, valid_state=None):
    from nodeconductor.structure import models

    project = resource.service_project_link.project
    is_admin = project.has_user(user, models.ProjectRole.ADMINISTRATOR) \
        or project.customer.has_user(user, models.CustomerRole.OWNER)

    if not is_admin and not user.is_staff:
        raise PermissionDenied(
            "Only project administrator or staff allowed to perform this action.")

    if valid_state is not None:
        state = valid_state if isinstance(valid_state, (list, tuple)) else [valid_state]
        if state and resource.state not in state:
            message = "Performing %s operation is not allowed for resource in its current state"
            raise IncorrectStateException(message % operation_name)
