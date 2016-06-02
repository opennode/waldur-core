# Django test settings for nodeconductor project.
from nodeconductor.server.base_settings import *

SECRET_KEY = 'test-key'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

INSTALLED_APPS += (
    'nodeconductor.quotas.tests',
    'nodeconductor.structure.tests',
)

ROOT_URLCONF = 'nodeconductor.structure.tests.urls'

BROKER_URL = 'sqla+sqlite:///:memory:'
CELERY_RESULT_BACKEND = 'db+sqlite:///:memory:'

NODECONDUCTOR.update({
    'MONITORING': {
        'ZABBIX': {
            'server': "http://127.0.0.1:8888/zabbix",
            'username': "admin",
            'password': "zabbix",

            'interface_parameters': {"ip": "0.0.0.0", "main": 1, "port": "10050", "type": 1, "useip": 1, "dns": ""},
            'templateid': '10106',
            'groupid': '8',
            'default_service_parameters': {'algorithm': 1, 'showsla': 1, 'sortorder': 1, 'goodsla': 95},
        }
    },
})
