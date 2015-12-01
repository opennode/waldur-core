from __future__ import unicode_literals

import unittest

from nodeconductor.support.serializers import CommentSerializer


class JiraCommentAuthorSerializerTest(unittest.TestCase):

    def test_parsing(self):
        username = "Walter"
        uuid = '1c3323fc4ae44120b57ec40dea1be6e6'
        body = "Hello, world!"
        comment = {"body": "Comment posted by user {} ({})\n{}".format(username, uuid, body)}

        expected = {
            'author': {
                'displayName': username,
                'uuid': uuid
            },
            'body': body
        }

        serializer = CommentSerializer(instance=comment)
        self.assertEqual(expected, serializer.data)
