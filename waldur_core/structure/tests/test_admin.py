import json
import copy

from django.test import TestCase

from waldur_core.structure.admin import ServiceSettingsAdminForm, PrivateServiceSettingsAdmin
from waldur_core.structure.models import PrivateServiceSettings
from waldur_core.structure.tests.serializers import ServiceSerializer
from waldur_core.structure.utils import get_all_services_field_info


class override_serializer(object):
    def __init__(self, value):
        self.value = value
        self.required = copy.copy(ServiceSerializer.Meta.required_fields)

        if ServiceSerializer.SERVICE_ACCOUNT_FIELDS is not NotImplemented:
            self.fields = copy.copy(ServiceSerializer.SERVICE_ACCOUNT_FIELDS)
        else:
            self.fields = NotImplemented

        if ServiceSerializer.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
            self.extra_fields = copy.copy(ServiceSerializer.SERVICE_ACCOUNT_EXTRA_FIELDS)
        else:
            self.extra_fields = NotImplemented

    def __enter__(self):
        ServiceSerializer.Meta.required_fields = self.value['required']
        ServiceSerializer.SERVICE_ACCOUNT_FIELDS = {k: '' for k in self.value['fields']}
        ServiceSerializer.SERVICE_ACCOUNT_EXTRA_FIELDS = {k: '' for k in self.value['extra_fields']}
        return ServiceSerializer

    def __exit__(self, exc_type, exc_value, traceback):
        ServiceSerializer.Meta.required_fields = self.required
        ServiceSerializer.SERVICE_ACCOUNT_FIELDS = self.fields
        ServiceSerializer.SERVICE_ACCOUNT_EXTRA_FIELDS = self.extra_fields


class ServiceSettingsAdminFormTest(ServiceSettingsAdminForm):
    class Meta:
        model = PrivateServiceSettings
        fields = PrivateServiceSettingsAdmin.fields


class AdminTest(TestCase):
    def setUp(self):
        super(AdminTest, self).setUp()
        self.service = 'Test'
        get_all_services_field_info.cache_clear()

    def test_required_field_form_correctly(self):
        with override_serializer({'required': ['backend_url'],
                                  'fields': ['backend_url'],
                                  'extra_fields': []}):
            options = json.dumps({})
            form = ServiceSettingsAdminFormTest({'type': self.service, 'name': 'test', 'state': 1,
                                                 'username': 'test', 'password': 'xxx', 'options': options,
                                                 'backend_url': 'http://test.net'})
            self.assertTrue(form.is_valid())

    def test_required_field_form_incorrectly(self):
        with override_serializer({'required': ['backend_url'],
                                  'fields': ['backend_url'],
                                  'extra_fields': []}):
            options = json.dumps({})
            form = ServiceSettingsAdminFormTest({'type': self.service, 'name': 'test', 'state': 1,
                                                 'username': 'test', 'password': 'xxx', 'options': options})
            self.assertFalse(form.is_valid())

    def test_required_extra_field_form_correctly(self):
        with override_serializer({'required': ['tenant'],
                                  'fields': [],
                                  'extra_fields': ['tenant']}):
            options = json.dumps({'tenant': 1})
            form = ServiceSettingsAdminFormTest({'type': self.service, 'name': 'test', 'state': 1,
                                                 'username': 'test', 'password': 'xxx', 'options': options})
            self.assertTrue(form.is_valid())

    def test_required_extra_field_form_incorrectly(self):
        with override_serializer({'required': ['tenant'],
                                  'fields': [],
                                  'extra_fields': ['tenant']}):
            options = json.dumps({})
            form = ServiceSettingsAdminFormTest({'type': self.service, 'name': 'test', 'state': 1,
                                                 'username': 'test', 'password': 'xxx', 'options': options})
            self.assertFalse(form.is_valid())
