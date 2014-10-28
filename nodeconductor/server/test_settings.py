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

OPENSTACK_CREDENTIALS = {
    'http://example.com:5000/v2': {
        'username': 'admin',
        'password': 'password',
    },
}
