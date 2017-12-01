# Django test settings for Waldur Core.
from waldur_core.server.doc_settings import *

MEDIA_ROOT = '/tmp/'

INSTALLED_APPS += (
    'waldur_core.quotas.tests',
    'waldur_core.structure.tests',
)

ROOT_URLCONF = 'waldur_core.structure.tests.urls'
