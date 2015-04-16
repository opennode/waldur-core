
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
