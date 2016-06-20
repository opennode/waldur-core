# Django settings for nodeconductor project
from nodeconductor.server.base_settings import *

import os
import warnings

from ConfigParser import RawConfigParser

conf_dir = '/etc/nodeconductor'
data_dir = '/usr/share/nodeconductor'
work_dir = '/var/lib/nodeconductor'

config = RawConfigParser()
config.read(os.path.join(conf_dir, 'settings.ini'))

# If these sections and/or options are not set, these values are used as defaults
config_defaults = {
    'global': {
        'db_backend': 'sqlite3',
        'debug': 'false',
        'media_root': os.path.join(work_dir, 'media'),
        'owner_can_manage_customer': 'false',
        'secret_key': '',
        'show_all_users': 'true',
        'static_root': os.path.join(data_dir, 'static'),
        'template_debug': 'false',
    },
    'auth': {
        'token_lifetime': 3600,
    },
    'celery': {
        'broker_url': 'redis://localhost',
        'result_backend_url': 'redis://localhost',
    },
    'elasticsearch': {
        # This location is RHEL7-specific, may be different on other platforms
        'ca_certs': '/etc/pki/tls/certs/ca-bundle.crt',  # only has effect if veryfy_certs is true
        'host': '',
        'password': '',
        'port': '9200',
        'protocol': 'http',
        'username': '',
        'verify_certs': 'true',  # only has effect if protocol is 'https'
    },
    'events': {
        'hook': 'false',
        'log_file': '',  # empty to disable logging events to file
        'log_level': 'INFO',
        'logserver_host': '',
        'logserver_port': 5959,
        'syslog': 'false',
    },
    'logging': {
        'admin_email': '',  # empty to disable sending errors to admin by email
        'log_file': '',  # empty to disable logging to file
        'log_level': 'INFO',
        'syslog': 'false',
    },
    'mysql': {
        'host': 'localhost',
        'name': 'nodeconductor',
        'password': 'nodeconductor',
        'port': '3306',
        'user': 'nodeconductor',
    },
    'openstack': {
        'auth_url': '',
        'cpu_overcommit_ratio': 1,
    },
    'rest_api': {
        'cors_allowed_domains': 'localhost,127.0.0.1',
    },
    'sentry': {
        'dsn': '',  # raven package is needed for this to work
    },
    'sqlite3': {
        'path': os.path.join(work_dir, 'db.sqlite3'),
    },
}

for section, options in config_defaults.items():
    if not config.has_section(section):
        config.add_section(section)
    for option, value in options.items():
        if not config.has_option(section, option):
            config.set(section, option, value)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config.get('global', 'secret_key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config.getboolean('global', 'debug')
for tmpl in TEMPLATES:
    tmpl.setdefault('OPTIONS', {})
    tmpl['OPTIONS']['debug'] = config.getboolean('global', 'template_debug')

# For security reason disable browsable API rendering in production
if not DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = ('rest_framework.renderers.JSONRenderer',)

MEDIA_ROOT = config.get('global', 'media_root')

ALLOWED_HOSTS = ['*']

#
# Application definition
#

# Database
# See also: https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {
    # Requirements for MySQL ('HOST', 'NAME', 'USER' and 'PASSWORD' are configured below):
    #  - MySQL server running and accessible on 'HOST':'PORT'
    #  - User 'USER' created and can login to MySQL server using password 'PASSWORD'
    #  - Database 'NAME' created with all privileges granted to user 'USER'
    #  - MySQL-python installed: https://pypi.python.org/pypi/MySQL-python
    #
    # Example: create database, user and grant privileges:
    #
    #   CREATE DATABASE nodeconductor CHARACTER SET = utf8;
    #   CREATE USER 'nodeconductor'@'%' IDENTIFIED BY 'nodeconductor';
    #   GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'%';
    #
    # Example: install MySQL-python in CentOS:
    #
    #   yum install MySQL-python
    #
    'default': {}
}

for prop in ('password', 'username', 'tenant_name'):
    if config.has_option('openstack', prop):
        warnings.warn("openstack.%s property in settings.ini is no longer supported and will be ignored" % prop)

if config.has_option('global', 'enable_order_processing'):
    warnings.warn(
        "global.enable_order_processing property in settings.ini is "
        "no longer supported and will be ignored")

if config.get('global', 'db_backend') == 'mysql':
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config.get('mysql', 'name'),
        'HOST': config.get('mysql', 'host'),
        'PORT': config.get('mysql', 'port'),
        'USER': config.get('mysql', 'user'),
        'PASSWORD': config.get('mysql', 'password'),
    }
elif config.has_section('sqlite3'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': config.get('sqlite3', 'path'),
    }

if config.has_section('billing'):
    warnings.warn(
        "[billing] section in settings.ini is no longer supported and will be ignored")

# Logging
# See also: https://docs.djangoproject.com/en/1.8/ref/settings/#logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,  # fixes Celery beat logging

    # Filters
    # Filter provides additional control over which log records are passed from logger to handler.
    # See also: https://docs.djangoproject.com/en/1.8/topics/logging/#filters
    'filters': {
        # Filter out only events (user-facing messages)
        'is-event': {
            '()': 'nodeconductor.logging.log.RequireEvent',
        },
        # Filter out only non-events (not user-facing messages)
        'is-not-event': {
            '()': 'nodeconductor.logging.log.RequireNotEvent',
        },
    },

    # Formatters
    # Formatter describes the exact format of the log entry.
    # See also: https://docs.djangoproject.com/en/1.8/topics/logging/#formatters
    'formatters': {
        'message-only': {
            'format': '%(message)s',
        },
        'simple': {
            'format': '%(asctime)s %(levelname)s %(message)s',
        },
    },

    # Handlers
    # Handler determines what happens to each message in a logger.
    # See also: https://docs.djangoproject.com/en/1.8/topics/logging/#handlers
    'handlers': {
        # Send logs to admins by email
        # See also: https://docs.djangoproject.com/en/1.8/topics/logging/#django.utils.log.AdminEmailHandler
        'email-admins': {
            'class': 'django.utils.log.AdminEmailHandler',
            'level': 'ERROR',
        },
        # Write logs to file
        # See also: https://docs.python.org/2/library/logging.handlers.html#watchedfilehandler
        'file': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': '/dev/null',
            'filters': ['is-not-event'],
            'formatter': 'simple',
            'level': config.get('logging', 'log_level').upper(),
        },
        'file-event': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': '/dev/null',
            'filters': ['is-event'],
            'formatter': 'simple',
            'level': config.get('events', 'log_level').upper(),
        },
        # Forward logs to syslog
        # See also: https://docs.python.org/2/library/logging.handlers.html#sysloghandler
        'syslog': {
            'class': 'logging.handlers.SysLogHandler',
            'filters': ['is-not-event'],
            'formatter': 'message-only',
            'level': config.get('logging', 'log_level').upper(),
        },
        'syslog-event': {
            'class': 'logging.handlers.SysLogHandler',
            'filters': ['is-event'],
            'formatter': 'message-only',
            'level': config.get('logging', 'log_level').upper(),
        },
        # Send logs to log server
        # Note that nodeconductor.logging.log.TCPEventHandler does not support exernal formatters
        'tcp': {
            'class': 'nodeconductor.logging.log.TCPEventHandler',
            'filters': ['is-not-event'],
            'level': config.get('events', 'log_level').upper(),
        },
        'tcp-event': {
            'class': 'nodeconductor.logging.log.TCPEventHandler',
            'filters': ['is-event'],
            'level': config.get('events', 'log_level').upper(),
        },
        'hook': {
            'class': 'nodeconductor.logging.log.HookHandler',
            'filters': ['is-event'],
            'level': config.get('events', 'log_level').upper()
        }
    },

    # Loggers
    # A logger is the entry point into the logging system.
    # Each logger is a named bucket to which messages can be written for processing.
    # See also: https://docs.djangoproject.com/en/1.8/topics/logging/#loggers
    #
    # Default logger configuration
    'root': {
        'level': 'INFO',
    },
    # Default configuration can be overridden on per-module basis
    'loggers': {
        'django': {
            'handlers': [],
        },
        'nodeconductor': {
            'handlers': [],
            'level': config.get('logging', 'log_level').upper(),
        },
        'requests': {
            'handlers': [],
            'level': 'WARNING',
        },
    },
}

if config.get('logging', 'admin_email') != '':
    ADMINS += (('Admin', config.get('logging', 'admin_email')),)
    LOGGING['loggers']['nodeconductor']['handlers'].append('email-admins')

if config.get('logging', 'log_file') != '':
    LOGGING['handlers']['file']['filename'] = config.get('logging', 'log_file')
    LOGGING['loggers']['django']['handlers'].append('file')
    LOGGING['loggers']['nodeconductor']['handlers'].append('file')

if config.getboolean('logging', 'syslog'):
    LOGGING['handlers']['syslog']['address'] = '/dev/log'
    LOGGING['loggers']['django']['handlers'].append('syslog')
    LOGGING['loggers']['nodeconductor']['handlers'].append('syslog')

if config.get('events', 'log_file') != '':
    LOGGING['handlers']['file-event']['filename'] = config.get('events', 'log_file')
    LOGGING['loggers']['nodeconductor']['handlers'].append('file-event')

if config.get('events', 'logserver_host') != '':
    LOGGING['handlers']['tcp-event']['host'] = config.get('events', 'logserver_host')
    LOGGING['handlers']['tcp-event']['port'] = config.getint('events', 'logserver_port')
    LOGGING['loggers']['nodeconductor']['handlers'].append('tcp-event')

if config.getboolean('events', 'syslog'):
    LOGGING['handlers']['syslog-event']['address'] = '/dev/log'
    LOGGING['loggers']['nodeconductor']['handlers'].append('syslog-event')

if config.getboolean('events', 'hook'):
    LOGGING['loggers']['nodeconductor']['handlers'].append('hook')

# Static files
# See also: https://docs.djangoproject.com/en/1.8/ref/settings/#static-files

STATIC_ROOT = config.get('global', 'static_root')

# Django CORS headers
# See also: https://github.com/ottoyiu/django-cors-headers

CORS_ALLOW_CREDENTIALS = True

CORS_EXPOSE_HEADERS = (
    'x-result-count',
    'Link',
)

CORS_ORIGIN_ALLOW_ALL = False
CORS_ORIGIN_WHITELIST = tuple(i.strip() for i in config.get('rest_api', 'cors_allowed_domains').split(','))

INSTALLED_APPS = (
    'corsheaders',
) + INSTALLED_APPS

MIDDLEWARE_CLASSES = (
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
) + MIDDLEWARE_CLASSES

# Celery
# See also: http://docs.celeryproject.org/en/latest/getting-started/brokers/index.html#broker-instructions
# See also: http://docs.celeryproject.org/en/latest/configuration.html#broker-url
BROKER_URL = config.get('celery', 'broker_url')

# See also: http://docs.celeryproject.org/en/latest/configuration.html#celery-result-backend
CELERY_RESULT_BACKEND = config.get('celery', 'result_backend_url')

for app in INSTALLED_APPS:
    if app.startswith('nodeconductor_'):
        LOGGING['loggers'][app] = LOGGING['loggers']['nodeconductor']

# NodeConductor internal configuration
# See also: http://nodeconductor.readthedocs.org/en/stable/guide/intro.html#id1
NODECONDUCTOR.update({
    'DEFAULT_SECURITY_GROUPS': (
        {
            'name': 'icmp',
            'description': 'Security group for ICMP',
            'rules': (
                {
                    'protocol': 'icmp',
                    'cidr': '0.0.0.0/0',
                    'icmp_type': -1,
                    'icmp_code': -1,
                },
            ),
        },
        {
            'name': 'ssh',
            'description': 'Security group for SSH',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 22,
                    'to_port': 22,
                },
            ),
        },
        {
            'name': 'http',
            'description': 'Security group for HTTP',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 80,
                    'to_port': 80,
                },
            ),
        },
        {
            'name': 'https',
            'description': 'Security group for HTTPS',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 443,
                    'to_port': 443,
                },
            ),
        },
        {
            'name': 'rdp',
            'description': 'Security group for RDP',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 3389,
                    'to_port': 3389,
                },
            ),
        },
        {
            'name': 'postgresql',
            'description': 'Security group for PostgreSQL PaaS service',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 22,
                    'to_port': 22,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 5432,
                    'to_port': 5432,
                },
                {
                    'protocol': 'icmp',
                    'cidr': '0.0.0.0/0',
                    'icmp_type': -1,
                    'icmp_code': -1,
                },
            ),
        },
        {
            'name': 'wordpress',
            'description': 'Security group for WordPress PaaS service',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 22,
                    'to_port': 22,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 80,
                    'to_port': 80,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 443,
                    'to_port': 443,
                },
            ),
        },
        {
            'name': 'zimbra',
            'description': 'Security group for Zimbra PaaS service',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 22,
                    'to_port': 22,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 25,
                    'to_port': 25,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 465,
                    'to_port': 465,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 110,
                    'to_port': 110,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 995,
                    'to_port': 995,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 143,
                    'to_port': 143,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 993,
                    'to_port': 993,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 80,
                    'to_port': 80,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 443,
                    'to_port': 443,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 7071,
                    'to_port': 7071,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 7025,
                    'to_port': 7025,
                },
            ),
        },
        {
            'name': 'zabbix',
            'description': 'Security group for Zabbix advanced monitoring',
            'rules': (
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 22,
                    'to_port': 22,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 80,
                    'to_port': 80,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 443,
                    'to_port': 443,
                },
                {
                    'protocol': 'tcp',
                    'cidr': '0.0.0.0/0',
                    'from_port': 3306,
                    'to_port': 3306,
                },
            ),
        },
    ),
    'OPENSTACK_OVERCOMMIT': (
        {
            'auth_url': config.get('openstack', 'auth_url'),
            'cpu_overcommit_ratio': config.getint('openstack', 'cpu_overcommit_ratio'),
        },
    ),
    'ELASTICSEARCH': {
        'username': config.get('elasticsearch', 'username'),
        'password': config.get('elasticsearch', 'password'),
        'host': config.get('elasticsearch', 'host'),
        'port': config.get('elasticsearch', 'port'),
        'protocol': config.get('elasticsearch', 'protocol'),
    },
    'TOKEN_LIFETIME': timedelta(seconds=config.getint('auth', 'token_lifetime')),
    'OWNER_CAN_MANAGE_CUSTOMER': config.getboolean('global', 'owner_can_manage_customer'),
    'SHOW_ALL_USERS': config.getboolean('global', 'show_all_users'),
})

if NODECONDUCTOR['ELASTICSEARCH']['protocol'] == 'https':
    NODECONDUCTOR['ELASTICSEARCH']['verify_certs'] = config.getboolean('elasticsearch', 'verify_certs')
    if NODECONDUCTOR['ELASTICSEARCH']['verify_certs']:
        NODECONDUCTOR['ELASTICSEARCH']['ca_certs'] = config.get('elasticsearch', 'ca_certs')

# Sentry integration
# See also: http://raven.readthedocs.org/en/latest/integrations/django.html#setup
if config.get('sentry', 'dsn') != '':
    INSTALLED_APPS = INSTALLED_APPS + ('raven.contrib.django.raven_compat',)
    RAVEN_CONFIG = {
        'dsn': config.get('sentry', 'dsn'),
    }

extensions = ('nodeconductor_plus.py', 'nodeconductor_saml2.py')
for extension_name in extensions:
    # optionally load extension configurations
    extension_conf_file_path = os.path.join(conf_dir, extension_name)
    if os.path.isfile(extension_conf_file_path):
        execfile(extension_conf_file_path)
