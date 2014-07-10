import factory

from nodeconductor.iaas import models


class TemplateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Template

    name = factory.Sequence(lambda n: 'template%s' % n)
