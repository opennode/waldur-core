from __future__ import unicode_literals

import unittest

from rest_framework import serializers
from nodeconductor.core.fields import JsonField
from nodeconductor.core.fields import TimestampField
from nodeconductor.core.fields import CommaSeparatedListField
from nodeconductor.core.serializers import Base64Field
from nodeconductor.core import utils

class Base64Serializer(serializers.Serializer):
    content = Base64Field()


class Base64FieldTest(unittest.TestCase):
    def test_text_gets_base64_encoded_on_serialization(self):
        serializer = Base64Serializer(instance={'content': 'hello'})
        actual = serializer.data['content']

        self.assertEqual('aGVsbG8=', actual)

    def test_text_remains_base64_encoded_on_deserialization(self):
        serializer = Base64Serializer(data={'content': 'Zm9vYmFy'})

        self.assertTrue(serializer.is_valid())

        actual = serializer.validated_data['content']

        self.assertEqual('Zm9vYmFy', actual)

    def test_deserialization_fails_validation_on_incorrect_base64(self):
        serializer = Base64Serializer(data={'content': '***NOT-BASE-64***'})

        self.assertFalse(serializer.is_valid())
        self.assertIn('content', serializer.errors,
                      'There should be errors for content field')
        self.assertIn('This field should a be valid Base64 encoded string.',
                      serializer.errors['content'])


class JsonSerializer(serializers.Serializer):
    content = JsonField()


class JsonFieldTest(unittest.TestCase):
    def test_dict_gets_parsed_as_dict_on_serialization(self):
        serializer = JsonSerializer(instance={'content': {u'key': u'value'}})
        actual = serializer.data['content']

        self.assertEqual({u'key': u'value'}, actual)

    def test_text_gets_json_parsed_on_deserialization(self):
        serializer = JsonSerializer(data={'content': '{"key": "value"}'})

        self.assertTrue(serializer.is_valid())

        actual = serializer.validated_data['content']

        self.assertEqual({u'key': u'value'}, actual)

    def test_deserialization_fails_validation_on_incorrect_json(self):
        serializer = JsonSerializer(data={'content': '***NOT-JSON***'})

        self.assertFalse(serializer.is_valid())
        self.assertIn('content', serializer.errors,
                      'There should be errors for content field')
        self.assertIn('This field should a be valid JSON string.',
                      serializer.errors['content'])


class TimestampSerializer(serializers.Serializer):
    content = TimestampField()


class TimestampFieldTest(unittest.TestCase):
    def setUp(self):
        self.datetime = utils.timeshift(days=-1)
        self.timestamp = utils.datetime_to_timestamp(self.datetime)

    def test_datetime_serialized_as_timestamp(self):
        serializer = TimestampSerializer(instance={'content': self.datetime})
        actual = serializer.data['content']
        self.assertEqual(self.timestamp, actual)

    def test_timestamp_parsed_as_datetime(self):
        serializer = TimestampSerializer(data={'content': str(self.timestamp)})
        self.assertTrue(serializer.is_valid())
        actual = serializer.validated_data['content']
        self.assertEqual(self.datetime, actual)

    def test_incorrect_timestamp(self):
        serializer = TimestampSerializer(data={'content': 'NOT_A_UNIX_TIMESTAMP'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('content', serializer.errors,
                      'There should be errors for content field')
        self.assertIn('This field should be valid UNIX timestamp.',
                      serializer.errors['content'])


class CommaSeparatedListFieldSerializer(serializers.Serializer):
    content = CommaSeparatedListField(choices=('cpu', 'memory', 'storage'))


class CommaSeparatedListFieldTest(unittest.TestCase):
    def test_parse_correct_list(self):
        serializer = CommaSeparatedListFieldSerializer(data={'content': 'cpu, memory'})
        self.assertTrue(serializer.is_valid())
        actual = serializer.validated_data['content']
        self.assertEqual(['cpu', 'memory'], actual)

    def test_parse_incorrect_list_item(self):
        serializer = CommaSeparatedListFieldSerializer(data={'content': 'INVALID_LIST_ITEM'})
        self.assertFalse(serializer.is_valid())
