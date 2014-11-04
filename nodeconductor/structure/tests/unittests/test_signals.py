from django.tests import TestCase

from nodeconductor.structure import models
from nodeconductor.structure.tests import factories


class ProjectSignalsTest(TestCase):

    def setUp(self):
        self.project = factories.ProjectFactory()

    def test_admin_project_role_is_created_upon_project_creation(self):
        self.assertTrue(self.project.roles.filter(role_type=models.ProjectRole.ADMINISTRATOR).exists(),
                        'Administrator role should have been created')

    def test_manager_project_role_is_created_upon_project_creation(self):
        self.assertTrue(self.project.roles.filter(role_type=models.ProjectRole.MANAGER).exists(),
                        'Manager role should have been created')


class ProjectGroupSignalsTest(TestCase):

    def setUp(self):
        self.project_group = factories.ProjectGroupFactory()

    def test_group_manager_role_is_created_upon_project_group_creation(self):
        self.assertTrue(self.project_group.roles.filter(role_type=models.ProjectGroupRole.MANAGER).exists(),
                        'Group manager role should have been created')
