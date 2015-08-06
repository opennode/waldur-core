from django.test import TestCase

from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class LicenseTest(TestCase):

    def setUp(self):
        """
        In setup we will create:
        license, template, instance, project and project role.
        """
        # license and template
        self.license = factories.TemplateLicenseFactory()
        self.template = factories.TemplateFactory()
        self.license.templates.add(self.template)
        # project and project group
        self.project = structure_factories.ProjectFactory()
        self.project_group = structure_factories.ProjectGroupFactory()
        self.project_group.projects.add(self.project)
        # cloud and image
        self.cloud = factories.CloudFactory()
        factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
        self.image = factories.ImageFactory(cloud=self.cloud, template=self.template)

    def test_get_projects(self):
        structure_factories.ProjectFactory()
        self.assertSequenceEqual(self.license.get_projects(), [self.project])

    def test_get_projects_groups(self):
        structure_factories.ProjectGroupFactory()
        self.assertSequenceEqual(self.license.get_projects_groups(), [self.project_group])


class InstanceTest(TestCase):

    def test_init_instance_licenses(self):
        template = factories.TemplateFactory()
        template_license = factories.TemplateLicenseFactory()
        template.template_licenses.add(template_license)
        instance = factories.InstanceFactory(template=template)
        self.assertEqual(instance.instance_licenses.count(), 1)
        instance_license = instance.instance_licenses.all()[0]
        self.assertEqual(instance_license.template_license, template_license)
