"""
Django base settings for nodeconductor project.
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))


DEBUG = False

TEMPLATE_DEBUG = False

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'nodeconductor.core',
    'nodeconductor.structure',
    'nodeconductor.cloud',
    'nodeconductor.iaas',
    'nodeconductor.ldapsync',

    # Template overrides need to happen before admin is imported.
    'django.contrib.admin',

    'rest_framework',
    'rest_framework.authtoken',
    'south',
    'background_task',

    'permission',
    'taggit'
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

REST_FRAMEWORK = {
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_MODEL_SERIALIZER_CLASS': 'rest_framework.serializers.HyperlinkedModelSerializer',
    'DEFAULT_FILTER_BACKENDS': ('rest_framework.filters.DjangoFilterBackend',),
    'PAGINATE_BY_PARAM': 'page_size',
    'MAX_PAGINATE_BY': 100,
    'PAGINATE_BY': 10
}

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'permission.backends.PermissionBackend',
    'djangosaml2.backends.Saml2Backend',
)

ANONYMOUS_USER_ID = None

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'nodeconductor', 'templates'),
)

SOUTH_MIGRATION_MODULES = {
    'taggit': 'taggit.south_migrations',
}

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

NODE_CONDUCTOR = {
    'FILTERED_RELATIONS': ('customer', 'project'),
}

SAML_CREATE_UNKNOWN_USER = True
