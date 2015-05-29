
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


class ServiceBackend(object):
    """ Basic service backed with only common methods pre-defined. """

    def sync(self):
        raise NotImplementedError

    def provision(self, resource, *args, **kwargs):
        raise NotImplementedError

    def destroy(self, resource):
        raise NotImplementedError

    def stop(self, resource):
        raise NotImplementedError

    def start(self, resource):
        raise NotImplementedError

    def restart(self, resource):
        raise NotImplementedError

    def add_ssh_key(self, ssh_key):
        raise NotImplementedError

    def remove_ssh_key(self, ssh_key):
        raise NotImplementedError

    @staticmethod
    def gb2mb(val):
        return val * 1024 if val else 0

    @staticmethod
    def tb2mb(val):
        return val * 1024 * 1024 if val else 0

    @staticmethod
    def mb2gb(val):
        return val / 1024 if val else 0

    @staticmethod
    def mb2tb(val):
        return val / 1024 / 1024 if val else 0
