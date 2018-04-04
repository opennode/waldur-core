import copy
import json

from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from waldur_core.structure.admin import PrivateServiceSettingsAdmin
from waldur_core.structure.models import PrivateServiceSettings
from waldur_core.structure.tests.serializers import ServiceSerializer
from waldur_core.structure.utils import get_all_services_field_info, FieldInfo


class MockRequest:
    pass


class MockSuperUser:
    def has_perm(self, perm):
        return True


request = MockRequest()
request.user = MockSuperUser()


class override_serializer(object):
    def __init__(self, field_info):
        self.field_info = field_info
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
        ServiceSerializer.Meta.required_fields = self.field_info.fields_required
        ServiceSerializer.SERVICE_ACCOUNT_FIELDS = {
            field: ''
            for field in self.field_info.fields
        }
        ServiceSerializer.SERVICE_ACCOUNT_EXTRA_FIELDS = {
            field: ''
            for field in self.field_info.extra_fields_required
        }
        return ServiceSerializer

    def __exit__(self, *args):
        ServiceSerializer.Meta.required_fields = self.required
        ServiceSerializer.SERVICE_ACCOUNT_FIELDS = self.fields
        ServiceSerializer.SERVICE_ACCOUNT_EXTRA_FIELDS = self.extra_fields


class ServiceSettingAdminTest(TestCase):
    def setUp(self):
        super(ServiceSettingAdminTest, self).setUp()
        get_all_services_field_info.cache_clear()

    def test_if_required_field_value_is_provided_form_is_valid(self):
        fields = FieldInfo(
            fields_required=['backend_url'],
            fields=['backend_url'],
            extra_fields_required=[]
        )

        data = self.get_valid_data(backend_url='http://test.net')
        self.assert_form_valid(fields, data)

    def test_if_required_field_value_is_not_provided_form_is_invalid(self):
        fields = FieldInfo(
            fields_required=['backend_url'],
            fields=['backend_url'],
            extra_fields_required=[]
        )

        data = self.get_valid_data()
        self.assert_form_invalid(fields, data)

    def test_if_required_extra_field_value_is_provided_form_is_valid(self):
        fields = FieldInfo(
            fields_required=['tenant'],
            fields=[],
            extra_fields_required=['tenant']
        )
        data = self.get_valid_data(options=json.dumps({'tenant': 1}))
        self.assert_form_valid(fields, data)

    def test_if_required_extra_field_value_is_not_provided_form_is_invalid(self):
        fields = FieldInfo(
            fields_required=['tenant'],
            fields=[],
            extra_fields_required=['tenant']
        )
        data = self.get_valid_data()
        self.assert_form_invalid(fields, data)

    def test_if_options_is_not_valid_json_form_is_invalid(self):
        fields = FieldInfo(
            fields_required=['tenant'],
            fields=[],
            extra_fields_required=['tenant']
        )
        data = self.get_valid_data(options='INVALID')
        self.assert_form_invalid(fields, data)

    def get_valid_data(self, **kwargs):
        data = {
            'type': 'Test',
            'name': 'test',
            'state': 1,
            'username': 'test',
            'password': 'xxx',
            'options': json.dumps({}),
        }
        data.update(kwargs)
        return data

    def form_is_valid(self, fields, data):
        with override_serializer(fields):
            site = AdminSite()
            model_admin = PrivateServiceSettingsAdmin(PrivateServiceSettings, site)
            form = model_admin.get_form(request)(data)
            return form.is_valid()

    def assert_form_valid(self, fields, data):
        self.assertTrue(self.form_is_valid(fields, data))

    def assert_form_invalid(self, fields, data):
        self.assertFalse(self.form_is_valid(fields, data))
