class MonitoringNotImplemented(NotImplementedError):
    pass


class Monitoring(object):
    """ Service-layer methods for monitoring """

    @classmethod
    def create_resource(cls, resource):
        """ Register new resource in monitoring system """
        raise MonitoringNotImplemented

    @classmethod
    def update_resource(cls, old_resource, new_resource):
        """ Update registered resource """
        raise MonitoringNotImplemented

    @classmethod
    def delete_resource(cls, resource):
        """ Remove resource from monitoring system """
        raise MonitoringNotImplemented


class MonitoringRegister(object):
    """ Register of monitored resources """

    _resources = {}

    @classmethod
    def register_resource(cls, resource_model, monitoring):
        cls._resources[resource_model] = monitoring

    @classmethod
    def get_resources(cls):
        return cls._resources

    @classmethod
    def get_resource_monitoring(cls, resource_model):
        return cls._resources[resource_model]
