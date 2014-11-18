# Django test settings for nodeconductor project.
from nodeconductor.server.base_settings import *

SECRET_KEY = 'test-key'

DEBUG = True
TEMPLATE_DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS += (
    'kombu.transport.django',  # Needed for broker backend
    'djcelery',  # Needed for result backend
)

BROKER_URL = 'django://'
CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'

NODECONDUCTOR = {
    'OPENSTACK_CREDENTIALS': (
        {
            'auth_url': 'http://example.com:5000/v2',
            'username': 'admin',
            'password': 'password',
            'tenant_name': 'admin',
        },
    ),
}
