
import base64
import hashlib


class CloudBackendError(Exception):
    """
    Base exception for errors occurring during backend communication.
    """
    pass


class CloudBackendInternalError(Exception):
    """
    Exception for errors in helpers.

    This exception will be raised if error happens, but cloud client
    did not raise any exception. It has be caught by public methods.
    """
    pass


def get_ssh_key_fingerprint(public_key):
    """ Validate SSH public key and return fingerprint """
    try:
        key = base64.b64decode(public_key.strip().split()[1].encode('ascii'))
        fp_plain = hashlib.md5(key).hexdigest()
    except:
        raise CloudBackendInternalError("SSH key is invalid: failed to generate fingerprint")

    return ':'.join(a + b for a, b in zip(fp_plain[::2], fp_plain[1::2]))
