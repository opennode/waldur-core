from django.test import TestCase

from nodeconductor.iaas.tests import factories
from nodeconductor.iaas import models
from nodeconductor.structure.tests import factories as structure_factories


class LicenseTest(TestCase):

    def setUp(self):
        """
        In setup we will create:
        license, template, instance, project and project role.
        """
        self.license = factories.LicenseFactory()
        self.template = factories.TemplateFactory()
        self.license.templates.add(self.template)
        self.project = structure_factories.ProjectFactory()
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        self.instance = factories.InstanceFactory(project=self.project, template=self.template)

    def test_projects(self):
        structure_factories.ProjectFactory()
        self.assertSequenceEqual(self.license.projects, [self.project.name])

    def test_projects_groups(self):
        structure_factories.ProjectGroupFactory()
        self.assertSequenceEqual(self.license.projects_groups, [self.project_group.name])
