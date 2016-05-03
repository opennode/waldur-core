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
        'token_lifetime': 1,
    },
    'celery': {
        'backup_schedule_execute_period': 600,
        'broker_url': 'redis://localhost',
        'cloud_account_pull_period': 3600,
        'cloud_project_membership_pull_period': 1800,
        'cloud_project_membership_quota_check_period': 86400,
        'expired_backup_delete_period': 600,
        'instance_monthly_sla_update_period': 300,
        'instance_provisioning_concurrency': 3,
        'instance_yearly_sla_update_period': 600,
        'instance_zabbix_sync_period': 1800,
        'recover_erred_services_period': 1800,
        'result_backend_url': 'redis://localhost',
        'service_statistics_update_period': 600,
    },
    'elasticsearch': {
        'host': '',
        'password': '',
        'port': '9200',
        'protocol': 'http',
        'username': '',
        'verify_certs': 'true',
        'ca_certs': '/etc/pki/tls/certs/ca-bundle.crt',  # RHEL7-specific, may be different on other platforms
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
    'zabbix': {
        'db_host': '',  # empty to disable Zabbix database access
        'db_name': 'zabbix',
        'db_password': 'nodeconductor',
        'db_port': '3306',
        'db_user': 'nodeconductor',
        'host_group_id': '',
        'host_template_id': '',
        'openstack_template_id': '',
        'password': '',
        'postgresql_template_id': '',
        'server_url': '',
        'username': '',
        'wordpress_template_id': '',
        'zimbra_template_id': '',
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
# See also: https://docs.djangoproject.com/en/1.7/ref/settings/#databases

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

if config.has_option('celery', 'recover_erred_cloud_memberships_period'):
    warnings.warn(
        "celery.recover_erred_cloud_memberships_period property in settings.ini is "
        "no longer supported and will be ignored in favor of celery.recover_erred_services_period")

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

# Zabbix database
if config.get('zabbix', 'db_host') != '':
    DATABASES['zabbix'] = {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': config.get('zabbix', 'db_host'),
        'NAME': config.get('zabbix', 'db_name'),
        'PORT': config.get('zabbix', 'db_port'),
        'USER': config.get('zabbix', 'db_user'),
        'PASSWORD': config.get('zabbix', 'db_password'),
    }

# Logging
# See also: https://docs.djangoproject.com/en/1.7/ref/settings/#logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,  # fixes Celery beat logging

    # Filters
    # Filter provides additional control over which log records are passed from logger to handler.
    # See also: https://docs.djangoproject.com/en/1.7/topics/logging/#filters
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
    # See also: https://docs.djangoproject.com/en/1.7/topics/logging/#formatters
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
    # See also: https://docs.djangoproject.com/en/1.7/topics/logging/#handlers
    'handlers': {
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
    # See also: https://docs.djangoproject.com/en/1.7/topics/logging/#loggers
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
# See also: https://docs.djangoproject.com/en/1.7/ref/settings/#static-files

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

# See also: http://docs.celeryproject.org/en/latest/configuration.html#celery-accept-content
# Not needed: set to 'json' in base_settings.py
#CELERY_ACCEPT_CONTENT = ['json']

# Regular tasks
# See also: http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html#entries
CELERYBEAT_SCHEDULE.update({
    'delete-expired-backups': {
        'task': 'nodeconductor.backup.tasks.delete_expired_backups',
        'schedule': timedelta(seconds=config.getint('celery', 'expired_backup_delete_period')),
        'args': (),
    },
    'execute-backup-schedules': {
        'task': 'nodeconductor.backup.tasks.execute_schedules',
        'schedule': timedelta(seconds=config.getint('celery', 'backup_schedule_execute_period')),
        'args': (),
    },
    'check-cloud-project-memberships-quotas': {
        'task': 'nodeconductor.iaas.tasks.iaas.check_cloud_memberships_quotas',
        'schedule': timedelta(seconds=config.getint('celery', 'cloud_project_membership_quota_check_period')),
        'args': (),
    },
    'sync-services': {
        'task': 'nodeconductor.iaas.sync_services',
        'schedule': timedelta(seconds=config.getint('celery', 'cloud_account_pull_period')),
        'args': (),
    },
    'recover-erred-services': {
        'task': 'nodeconductor.structure.recover_erred_services',
        'schedule': timedelta(seconds=config.getint('celery', 'recover_erred_services_period')),
        'args': (),
    },
    'pull-cloud-project-memberships': {
        'task': 'nodeconductor.iaas.tasks.iaas.pull_cloud_memberships',
        'schedule': timedelta(seconds=config.getint('celery', 'cloud_project_membership_pull_period')),
        'args': (),
    },
    'pull-service-statistics': {
        'task': 'nodeconductor.iaas.tasks.iaas.pull_service_statistics',
        'schedule': timedelta(seconds=config.getint('celery', 'service_statistics_update_period')),
        'args': (),
    },
    'sync-instances-with-zabbix': {
        'task': 'nodeconductor.iaas.tasks.iaas.sync_instances_with_zabbix',
        'schedule': timedelta(seconds=config.getint('celery', 'instance_zabbix_sync_period')),
        'args': (),
    },
    'update-instance-monthly-slas': {
        'task': 'nodeconductor.monitoring.tasks.update_instance_sla',
        'schedule': timedelta(seconds=config.getint('celery', 'instance_monthly_sla_update_period')),
        'args': ('monthly',),
    },
    'update-instance-yearly-slas': {
        'task': 'nodeconductor.monitoring.tasks.update_instance_sla',
        'schedule': timedelta(seconds=config.getint('celery', 'instance_yearly_sla_update_period')),
        'args': ('yearly',),
    },
})

for app in INSTALLED_APPS:
    if app.startswith('nodeconductor_'):
        LOGGING['loggers'][app] = LOGGING['loggers']['nodeconductor']

# NodeConductor throttling settings for celery tasks
CELERY_TASK_THROTTLING = {
    'nodeconductor.iaas.tasks.openstack.openstack_provision_instance': {
        'concurrency': config.getint('celery', 'instance_provisioning_concurrency'),
    },
}

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

    'MONITORING': {
        'ZABBIX': {
            'server': config.get('zabbix', 'server_url'),
            'username': config.get('zabbix', 'username'),
            'password': config.get('zabbix', 'password'),
            'templateid': config.get('zabbix', 'host_template_id'),
            'groupid': config.get('zabbix', 'host_group_id'),
            'interface_parameters': {
                'ip': '0.0.0.0',
                'main': 1,
                'port': '10050',
                'type': 1,
                'useip': 1,
                'dns': '',
            },
            'default_service_parameters': {
                'algorithm': 1,
                'sortorder': 1,
                'showsla': 1,
                'goodsla': 95,
            },
            'openstack-templateid': config.get('zabbix', 'openstack_template_id'),
            'postgresql-templateid': config.get('zabbix', 'postgresql_template_id'),
            'wordpress-templateid': config.get('zabbix', 'wordpress_template_id'),
            'zimbra-templateid': config.get('zabbix', 'zimbra_template_id'),
        }
    },
    'ELASTICSEARCH': {
        'username': config.get('elasticsearch', 'username'),
        'password': config.get('elasticsearch', 'password'),
        'host': config.get('elasticsearch', 'host'),
        'port': config.get('elasticsearch', 'port'),
        'protocol': config.get('elasticsearch', 'protocol'),
        'use_ssl': True if config.get('elasticsearch', 'protocol') == 'https' else False,
        'verify_certs': config.getboolean('elasticsearch', 'verify_certs'),
        'ca_certs': config.get('elasticsearch', 'ca_certs'),
    },
    'TOKEN_LIFETIME': timedelta(hours=config.getint('auth', 'token_lifetime')),

    'OWNER_CAN_MANAGE_CUSTOMER': config.getboolean('global', 'owner_can_manage_customer'),

    'SHOW_ALL_USERS': config.getboolean('global', 'show_all_users'),

})


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
