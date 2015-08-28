from django.contrib.auth import get_user_model

from nodeconductor.core.models import SshPublicKey


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
