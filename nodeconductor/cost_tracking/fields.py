from django.contrib.contenttypes.models import ContentType
from django.utils.lru_cache import lru_cache

from nodeconductor.core.fields import NaturalChoiceField
from nodeconductor.structure import SupportedServices


class ResourceTypeField(NaturalChoiceField):
    def __init__(self, **kwargs):
        super(ResourceTypeField, self).__init__(choices=self.get_choices(), **kwargs)

    def to_representation(self, value):
        assert isinstance(value, ContentType), 'Resource type should be instance of ContentType'
        return SupportedServices.get_name_for_model(value.model_class())

    @lru_cache(maxsize=1)
    def get_choices(self):
        resources = SupportedServices.get_resource_models().values()
        content_types = ContentType.objects.get_for_models(*resources).values()
        choices = [(ct, SupportedServices.get_name_for_model(ct.model_class())) for ct in content_types]
        # Order choices by model name
        choices.sort(key=lambda choice: choice[1])
        return choices
