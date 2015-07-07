default_app_config = 'nodeconductor.structure.apps.StructureConfig'


class ServiceBackendError(Exception):
    """ Base exception for errors occurring during backend communication. """
    pass


class ServiceBackendNotImplemented(NotImplementedError):
    pass


class ServiceBackend(object):
    """ Basic service backed with only common methods pre-defined. """

    def __init__(self, settings, **kwargs):
        pass

    def sync(self):
        raise ServiceBackendNotImplemented

    def sync_link(self, service_project_link):
        raise ServiceBackendNotImplemented

    def provision(self, resource, *args, **kwargs):
        raise ServiceBackendNotImplemented

    def destroy(self, resource):
        raise ServiceBackendNotImplemented

    def stop(self, resource):
        raise ServiceBackendNotImplemented

    def start(self, resource):
        raise ServiceBackendNotImplemented

    def restart(self, resource):
        raise ServiceBackendNotImplemented

    def add_ssh_key(self, ssh_key, service_project_link):
        raise ServiceBackendNotImplemented

    def remove_ssh_key(self, ssh_key, service_project_link):
        raise ServiceBackendNotImplemented

    def add_user(self, user, service_project_link):
        raise ServiceBackendNotImplemented

    def remove_user(self, user, service_project_link):
        raise ServiceBackendNotImplemented

    @staticmethod
    def gb2mb(val):
        return int(val * 1024) if val else 0

    @staticmethod
    def tb2mb(val):
        return int(val * 1024 * 1024) if val else 0

    @staticmethod
    def mb2gb(val):
        return val / 1024 if val else 0

    @staticmethod
    def mb2tb(val):
        return val / 1024 / 1024 if val else 0
