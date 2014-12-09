from django.test import TestCase
from mock import Mock

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
        self.assertEqual(instance_license.setup_fee, template_license.setup_fee)
        self.assertEqual(instance_license.monthly_fee, template_license.monthly_fee)


class TestInstanceCopySshPublicKeysAttribute(TestCase):

    def setUp(self):
        # given
        self.instance = factories.InstanceFactory.create()
        self.ssh_public_key = factories.SshPublicKeyFactory.build()

    def when(self):
        self.instance.ssh_public_key = self.ssh_public_key
        self.instance._copy_ssh_public_key_attributes()

    def test_ssh_public_key_name_is_copied(self):
        self.when()
        # then
        self.assertEqual(self.instance.ssh_public_key_name, self.ssh_public_key.name)

    def test_ssh_public_key_fingerprint_is_copied(self):
        self.when()
        # then
        self.assertEqual(self.instance.ssh_public_key_fingerprint, self.ssh_public_key.fingerprint)


class TestInstanceCopyFlavorAttributes(TestCase):

    def setUp(self):
        # given
        self.instance = factories.InstanceFactory.create()
        self.flavor = factories.FlavorFactory.build()

    def when(self):
        self.instance.flavor = self.flavor
        self.instance._copy_flavor_attributes()

    def test_flavor_ram_is_copied(self):
        self.when()
        # then
        self.assertEqual(self.instance.ram, self.flavor.ram)

    def test_flavor_disk_is_copied(self):
        self.when()
        # then
        self.assertEqual(self.instance.system_volume_size, self.flavor.disk)

    def test_flavor_cores_is_copied(self):
        self.when()
        # then
        self.assertEqual(self.instance.cores, self.flavor.cores)

    def test_flavor_cloud_is_copied(self):
        self.when()
        # then
        self.assertEqual(self.instance.cloud, self.flavor.cloud)


class TestInstanceCopyTemplateAttributes(TestCase):

    def setUp(self):
        # given
        self.instance = factories.InstanceFactory.create()
        self.template = factories.TemplateFactory.build()

    def when(self):
        self.instance.template = self.template
        self.instance._copy_template_attributes()

    def test_flavor_ram_is_copied(self):
        self.when()
        # then
        self.assertEqual(self.instance.agreed_sla, self.template.sla_level)


class TestInstanceSave(TestCase):

    def setUp(self):
        # given
        self.instance = factories.InstanceFactory.create()
        self.instance._copy_template_attributes = Mock()
        self.instance._init_instance_licenses = Mock()
        self.instance._copy_flavor_attributes = Mock()
        self.instance._copy_ssh_public_key_attributes = Mock()

    def when(self, create):
        if create:
            self.instance.uuid = None
            self.instance.pk = None
        self.instance.save()

    def test_copy_template_attributes_was_called_if_instance_was_created(self):
        self.when(create=True)
        #then
        self.instance._copy_template_attributes.assert_called_once_with()

    def test_copy_flavor_attributes_was_called_if_instance_was_created(self):
        self.when(create=True)
        #then
        self.instance._copy_flavor_attributes.assert_called_once_with()

    def test_copy_ssh_public_key_attributes_was_called_if_instance_was_created(self):
        self.when(create=True)
        #then
        self.instance._copy_ssh_public_key_attributes.assert_called_once_with()

    def test_init_instance_licenses_was_called_if_instance_was_created(self):
        self.when(create=True)
        #then
        self.instance._init_instance_licenses.assert_called_once_with()
