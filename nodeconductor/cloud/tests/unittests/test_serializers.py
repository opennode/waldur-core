from django.test import TestCase

from nodeconductor.cloud import serializers
from nodeconductor.cloud.tests import factories
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure import models as structure_models


class CloudSerializerTest(TestCase):

    def test_to_native(self):
        customer = structure_factories.CustomerFactory()
        owner = structure_factories.UserFactory()
        customer.add_user(owner, structure_models.CustomerRole.OWNER)
        admin = structure_factories.UserFactory()
        project = structure_factories.ProjectFactory(customer=customer)
        project.add_user(admin, structure_models.ProjectRole.ADMINISTRATOR)
        cloud = factories.CloudFactory(customer=customer)
        factories.CloudProjectMembershipFactory(project=project, cloud=cloud)

        serializer = serializers.CloudSerializer(cloud, context={'user': admin})
        self.assertEqual(len(serializer.to_native(cloud)), len(serializer.public_fields))

        serializer = serializers.CloudSerializer(cloud, context={'user': owner})
        self.assertGreater(len(serializer.to_native(cloud)), len(serializer.public_fields))
