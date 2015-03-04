default_app_config = 'nodeconductor.template.apps.TemplateConfig'


class TemplateStrategy(object):
    """ A parent class for the model-specific template strategies.
    """
    @classmethod
    def get_model(cls):
        raise NotImplementedError(
            'Implement get_model() that would return TemplateService inherited model.')

    @classmethod
    def get_serializer(cls):
        raise NotImplementedError(
            'Implement get_serializer() that would return TemplateService model serializer.')

    @classmethod
    def deploy(cls, backup_source):
        raise NotImplementedError(
            'Implement deploy() that would perform deploy of a service.')
