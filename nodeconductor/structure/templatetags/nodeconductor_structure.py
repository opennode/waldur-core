from django import template

from nodeconductor.structure import SupportedServices

register = template.Library()

@register.simple_tag
def service_settings():
    return SupportedServices.get_service_settings()
