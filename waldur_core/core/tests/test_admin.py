from django.test import TestCase

from waldur_core.core.admin import UserChangeForm
from waldur_core.structure.tests.factories import UserFactory


class UserAdminTest(TestCase):
    def change_user(self, **kwargs):
        user = UserFactory()
        form_for_data = UserChangeForm(instance=user)

        post_data = form_for_data.initial
        post_data.update(kwargs)

        form = UserChangeForm(instance=user, data=post_data)
        form.save()

        user.refresh_from_db()
        return user

    def test_civil_number_is_stripped(self):
        user = self.change_user(civil_number='  NEW_CIVIL_NUMBER  ')
        self.assertEqual(user.civil_number, 'NEW_CIVIL_NUMBER')

    def test_whitspace_civil_number_converts_to_none(self):
        user = self.change_user(civil_number='  ')
        self.assertEqual(user.civil_number, None)

    def test_empty_civil_number_converts_to_none(self):
        user = self.change_user(civil_number='')
        self.assertEqual(user.civil_number, None)
