# Django test settings for nodeconductor project.
from nodeconductor.server.doc_settings import *

INSTALLED_APPS += (
    'nodeconductor.quotas.tests',
    'nodeconductor.structure.tests',
)

ROOT_URLCONF = 'nodeconductor.structure.tests.urls'


# XXX: This option should be removed after itacloud assembly creation.
NODECONDUCTOR['IS_ITACLOUD'] = True
