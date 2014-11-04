from uuid import uuid4


class MockedTenant(object):

    def __init__(self, **kwargs):
        uuid = str(uuid4())
        self.enabled = kwargs.get('enabled', True)
        self.name = kwargs.get('name', 'tenant#%s' % uuid)
        self.description = kwargs.get('description', 'description for %s' % self.name)
        self.id = kwargs.get('id', uuid)


class KeystoneMockedClient(object):

    class tenants(object):

        @classmethod
        def create(cls, *args, **kwargs):
            return MockedTenant()
