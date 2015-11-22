# encoding: utf-8
from __future__ import unicode_literals

import factory
import factory.fuzzy

from rest_framework.reverse import reverse

from nodeconductor.template import models


class TemplateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Template

    name = factory.Sequence(lambda n: 'My Package %s' % n)
    description = factory.Sequence(lambda n: 'description %d' % n)
    icon_url = factory.Sequence(lambda n: 'http://example.com/%d.png' % n)
    is_active = True

    @classmethod
    def get_url(cls, template=None):
        template = template or TemplateFactory()

        return 'http://testserver' + reverse('template-detail', kwargs={'uuid': template.uuid})

    @classmethod
    def get_list_url(cls):
        return 'http://testserver' + reverse('template-list')
