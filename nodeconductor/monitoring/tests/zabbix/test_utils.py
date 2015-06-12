import unittest
from nodeconductor.core.utils import format_timeline


class TestFormatTimeline(unittest.TestCase):
    def test_list_converted_to_dict(self):
        expected = [
            {
                'from': 1433808000,
                'to': 1433894399,
                'vcpu_limit': 10,
                'vcpu_usage': 5
            }
        ]
        actual = format_timeline([
            (1433808000, 1433894399, 'vcpu_limit', 10),
            (1433808000, 1433894399, 'vcpu_usage', 5)
        ])
        self.assertEqual(expected, actual)
