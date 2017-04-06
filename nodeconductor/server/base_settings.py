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


ADMINS = ()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))

DEBUG = False

MEDIA_ROOT = '/media_root/'

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
    'nodeconductor.monitoring',
    'nodeconductor.quotas',
    'nodeconductor.structure',
    'nodeconductor.cost_tracking',
    'nodeconductor.users',

    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_swagger',

    'permission',
    'django_fsm',
    'reversion',
    'taggit',
    'jsoneditor',
)
INSTALLED_APPS += ADMIN_INSTALLED_APPS

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
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
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
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

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

ANONYMOUS_USER_ID = None

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'nodeconductor', 'templates')],
        'OPTIONS': {
            'context_processors': (
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
            ),
            'loaders': (
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ) + ADMIN_TEMPLATE_LOADERS,
            'builtins': ['permission.templatetags.permissionif'],
        },
    },
]

ROOT_URLCONF = 'nodeconductor.server.urls'

AUTH_USER_MODEL = 'core.User'

# Session
# https://docs.djangoproject.com/en/1.8/ref/settings/#sessions
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True

WSGI_APPLICATION = 'nodeconductor.server.wsgi.application'

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'nodeconductor', 'locale'),
)

LANGUAGES = (
    ('en', 'English'),
    ('et', 'Estonian'),
)

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/
STATIC_URL = '/static/'

# Celery
BROKER_URL = 'redis://localhost'
CELERY_RESULT_BACKEND = 'redis://localhost'

CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'

CELERY_QUEUES = {
    'tasks': {'exchange': 'tasks'},
    'heavy': {'exchange': 'heavy'},
    'background': {'exchange': 'background'},
}
CELERY_DEFAULT_QUEUE = 'tasks'
CELERY_ROUTES = ('nodeconductor.server.celery.PriorityRouter',)

CACHES = {
    'default': {
        'BACKEND': 'redis_cache.RedisCache',
        'LOCATION': 'redis://localhost',
        'OPTIONS': {
            'DB': 1,
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_CLASS': 'redis.BlockingConnectionPool',
            'PICKLE_VERSION': -1,
        },
    },
}

# Regular tasks
CELERYBEAT_SCHEDULE = {
    'pull-service-settings': {
        'task': 'nodeconductor.structure.ServiceSettingsListPullTask',
        'schedule': timedelta(minutes=30),
        'args': (),
    },
    'check-expired-permissions': {
        'task': 'nodeconductor.structure.check_expired_permissions',
        'schedule': timedelta(hours=24),
        'args': (),
    },
    'recalculate-price-estimates': {
        'task': 'nodeconductor.cost_tracking.recalculate_estimate',
        # To avoid bugs and unexpected behavior - do not re-calculate estimates
        # right in the end of the month.
        'schedule': crontab(minute=10),
        'args': (),
    },
    'close-alerts-without-scope': {
        'task': 'nodeconductor.logging.close_alerts_without_scope',
        'schedule': timedelta(minutes=30),
        'args': (),
    },
    'cleanup-alerts': {
        'task': 'nodeconductor.logging.alerts_cleanup',
        'schedule': timedelta(minutes=30),
        'args': (),
    },
    'check-threshold': {
        'task': 'nodeconductor.logging.check_threshold',
        'schedule': timedelta(minutes=30),
        'args': (),
    },
    'cancel-expired-invitations': {
        'task': 'nodeconductor.users.cancel_expired_invitations',
        'schedule': timedelta(hours=24),
        'args': (),
    },
}

# Logging
# Send verified request on webhook processing
VERIFY_WEBHOOK_REQUESTS = True


# Extensions
NODECONDUCTOR = {
    'EXTENSIONS_AUTOREGISTER': True,
    'TOKEN_KEY': 'x-auth-token',
    'TOKEN_LIFETIME': timedelta(hours=1),

    'SUSPEND_UNPAID_CUSTOMERS': False,
    'CLOSED_ALERTS_LIFETIME': timedelta(weeks=1),
    'INVITATION_LIFETIME': timedelta(weeks=1),
    'OWNERS_CAN_MANAGE_OWNERS': True,
    'BACKEND_FIELDS_EDITABLE': True,
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

    ext.update_settings(globals())


# Swagger
SWAGGER_SETTINGS = {
    # USE_SESSION_AUTH parameter should be equal to DEBUG parameter.
    # If it is True, LOGIN_URL and LOGOUT_URL must be specified.
    'USE_SESSION_AUTH': False,
    'APIS_SORTER': 'alpha',
    'JSON_EDITOR': True,
    'SECURITY_DEFINITIONS': {
        'api_key': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
        },
    },
}
