class MonitoringBackendNotImplemented(NotImplementedError):
    pass


class MonitoringBackend(object):
    """ Backend with basic monitoring methods """

    def create_resource(self, resource):
        raise MonitoringBackendNotImplemented
