"""
Django base settings for nodeconductor project.
"""
from __future__ import absolute_import

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import warnings

from datetime import timedelta
from celery.schedules import crontab

from nodeconductor.core import NodeConductorExtension
from nodeconductor.server.admin.settings import *

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))


DEBUG = False

TEMPLATE_DEBUG = False

MEDIA_ROOT = '/tmp/'

MEDIA_URL = '/media/'

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.humanize',
    'django.contrib.staticfiles',

    'nodeconductor.landing',
    'nodeconductor.logging',
    'nodeconductor.core',
    'nodeconductor.backup',
    'nodeconductor.template',
    'nodeconductor.monitoring',
    'nodeconductor.quotas',
    'nodeconductor.structure',
    'nodeconductor.cost_tracking',
    'nodeconductor.billing',
    'nodeconductor.openstack',
    # 'nodeconductor.oracle',
    'nodeconductor.iaas',
    'nodeconductor.support',
    'nodeconductor.ldapsync',
    # TODO: remove
    'nodeconductor_zabbix',

    'nodeconductor.testdata',

    'rest_framework',
    'rest_framework.authtoken',

    'permission',
    'django_fsm',
    'reversion',
)

INSTALLED_APPS += ADMIN_APPS

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'nodeconductor.logging.middleware.CaptureEventContextMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

REST_FRAMEWORK = {
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'nodeconductor.core.authentication.TokenAuthentication',
        'nodeconductor.core.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': ('rest_framework.filters.DjangoFilterBackend',),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'nodeconductor.core.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PAGINATION_CLASS': 'nodeconductor.core.pagination.LinkHeaderPagination',
    'PAGE_SIZE': 10,
    'EXCEPTION_HANDLER': 'nodeconductor.core.views.exception_handler',

    # Return native `Date` and `Time` objects in `serializer.data`
    'DATETIME_FORMAT': None,
    'DATE_FORMAT': None,
    'TIME_FORMAT': None,
}

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'permission.backends.PermissionBackend',
)

ANONYMOUS_USER_ID = None

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'nodeconductor', 'templates'),
    os.path.join(BASE_DIR, 'nodeconductor', 'billing', 'templates'),
    os.path.join(BASE_DIR, 'nodeconductor', 'landing', 'templates'),
)

ROOT_URLCONF = 'nodeconductor.server.urls'

AUTH_USER_MODEL = 'core.User'

WSGI_APPLICATION = 'nodeconductor.server.wsgi.application'

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

BROKER_URL = 'redis://localhost'
CELERY_RESULT_BACKEND = 'redis://localhost'

CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'

CELERY_QUEUES = {
    'tasks': {'exchange': 'tasks'},
    'heavy': {'exchange': 'heavy'},
}
CELERY_DEFAULT_QUEUE = 'tasks'
CELERY_ROUTES = ('nodeconductor.server.celery.PriorityRouter',)

# Regular tasks
CELERYBEAT_SCHEDULE = {
    'update-instance-monthly-slas': {
        'task': 'nodeconductor.monitoring.tasks.update_instance_sla',
        'schedule': timedelta(minutes=5),
        'args': ('monthly',),
    },
    'update-instance-yearly-slas': {
        'task': 'nodeconductor.monitoring.tasks.update_instance_sla',
        'schedule': timedelta(minutes=10),
        'args': ('yearly',),
    },

    'debit-customers': {
        'task': 'nodeconductor.billing.debit_customers',
        'schedule': crontab(hour=0, minute=30),
        'args': (),
    },

    'sync-services': {
        'task': 'nodeconductor.iaas.sync_services',
        'schedule': timedelta(minutes=60),
        'args': (),
    },

    'sync-service-settings': {
        'task': 'nodeconductor.structure.sync_service_settings',
        'schedule': timedelta(minutes=30),
        'args': (),
    },

    'recover-erred-services': {
        'task': 'nodeconductor.structure.recover_erred_services',
        'schedule': timedelta(minutes=45),
        'args': (),
    },

    'pull-service-statistics': {
        'task': 'nodeconductor.iaas.tasks.iaas.pull_service_statistics',
        'schedule': timedelta(minutes=15),
        'args': (),
    },
    'pull-cloud-project-memberships': {
        'task': 'nodeconductor.iaas.tasks.iaas.pull_cloud_memberships',
        'schedule': timedelta(minutes=30),
        'args': (),
    },

    'check-cloud-project-memberships-quotas': {
        'task': 'nodeconductor.iaas.tasks.iaas.check_cloud_memberships_quotas',
        'schedule': timedelta(minutes=1440),
        'args': (),
    },

    'sync-instances-with-zabbix': {
        'task': 'nodeconductor.iaas.tasks.iaas.sync_instances_with_zabbix',
        'schedule': timedelta(minutes=30),
        'args': (),
    },

    'create-zabbix-hosts-and-services': {
        'task': 'nodeconductor.iaas.tasks.zabbix.zabbix_create_host_and_service_for_all_instances',
        'schedule': timedelta(hours=1),
        'args': (),
    },

    'execute-backup-schedules': {
        'task': 'nodeconductor.backup.tasks.execute_schedules',
        'schedule': timedelta(minutes=10),
        'args': (),
    },

    'delete-expired-backups': {
        'task': 'nodeconductor.backup.tasks.delete_expired_backups',
        'schedule': timedelta(minutes=10),
        'args': (),
    },

    'pull-instances-installation-state': {
        'task': 'nodeconductor.iaas.tasks.zabbix.pull_instances_installation_state',
        'schedule': timedelta(minutes=1),
        'args': (),
    },

    'update-current-month-cost-projections': {
        'task': 'nodeconductor.cost_tracking.update_projected_estimate',
        'schedule': timedelta(hours=24),
        'args': (),
    },

    'update-today-usage': {
        'task': 'nodeconductor.cost_tracking.update_today_usage',
        'schedule': crontab(minute=10),
        'args': (),
    },

    'update-openstack-service-project-links-quotas': {
        'task': 'nodeconductor.structure.sync_service_project_links',
        'schedule': timedelta(minutes=30),
        'args': (),
    },

    'close-alerts-without-scope': {
        'task': 'nodeconductor.logging.close_alerts_without_scope',
        'schedule': timedelta(minutes=30),
        'args': (),
    }
}

CELERY_TASK_THROTTLING = {
    'nodeconductor.iaas.tasks.openstack.openstack_provision_instance': {
        'concurrency': 1,
        'retry_delay': 30,
    },
}

NODECONDUCTOR = {
    'EXTENSIONS_AUTOREGISTER': True,
    'ENABLE_ORDER_PROCESSING': False,
    'DEFAULT_SECURITY_GROUPS': (
        {
            'name': 'ssh',
            'description': 'Security group for secure shell access and ping',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 22,
                    'to_port': 22,
                },
                {
                    'protocol': 'icmp',
                    'cidr': '0.0.0.0/0',
                    'icmp_type': -1,
                    'icmp_code': -1,
                },
            ),
        },
    ),
    'JIRA_SUPPORT': {'dummy': True},
    'ELASTICSEARCH_DUMMY': True,
    'SUSPEND_UNPAID_CUSTOMERS': False,
    'TOKEN_KEY': 'x-auth-token',
}


for ext in NodeConductorExtension.get_extensions():
    INSTALLED_APPS += (ext.django_app(),)

    for name, task in ext.celery_tasks().items():
        if name in CELERYBEAT_SCHEDULE:
            warnings.warn(
                "Celery beat task %s from NodeConductor extension %s "
                "is overlapping with primary tasks definition" % (name, ext.django_app()))
        else:
            CELERYBEAT_SCHEDULE[name] = task

    for key, val in ext.Settings.__dict__.items():
        if not key.startswith('_'):
            globals()[key] = val
