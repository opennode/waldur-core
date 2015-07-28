# Django settings for nodeconductor project
from nodeconductor.server.base_settings import *

import os
import saml2
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
        'media_root': work_dir,
        'secret_key': '',
        'static_root': os.path.join(data_dir, 'static'),
        'template_debug': 'false',
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
        'port': '443',
        'protocol': 'https',
        'username': '',
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
    'saml2': {
        'acs_url': '',
        'attribute_map_civil_number': 'Civil number',
        'attribute_map_dir': os.path.join(conf_dir, 'saml2', 'attribute-maps'),
        'attribute_map_full_name': 'Full name',
        'attribute_map_native_name': 'Native name',
        'debug': 'false',
        'entity_id': 'saml-sp2',
        'idp_metadata_cert': '',
        'idp_metadata_file': os.path.join(conf_dir, 'saml2', 'idp-metadata.xml'),
        'idp_metadata_url': '',
        'log_file': '',  # empty to disable logging SAML2-related stuff to file
        'log_level': 'INFO',
    },
    'sentry': {
        'dsn': '',  # raven package is needed for this to work
    },
    'sqlite3': {
        'path': os.path.join(work_dir, 'db.sqlite3'),
    },
    'whmcs': {
        'api_url': '',
        'currency_code': 1,
        'currency_name': 'USD',
        'password': '',
        'username': '',
    },
    'zabbix': {
        'db_host': '',  # empty to disable Zabbix database access
        'db_name': 'zabbix',
        'db_password': 'nodeconductor',
        'db_port': '3306',
        'db_user': 'nodeconductor',
        'host_group_id': '',
        'host_template_id': '',
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

# These shouldn't be configurable by user -- see SAML2 section for details
config.set('saml2', 'cert_file', os.path.join(conf_dir, 'saml2', 'dummy.crt'))
config.set('saml2', 'key_file', os.path.join(conf_dir, 'saml2', 'dummy.pem'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config.get('global', 'secret_key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config.getboolean('global', 'debug')
TEMPLATE_DEBUG = config.getboolean('global', 'template_debug')

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
        'file-saml2': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': '/dev/null',
            'formatter': 'simple',
            'level': config.get('saml2', 'log_level').upper(),
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
        'djangosaml2': {
            'handlers': [],
        },
        'nodeconductor': {
            'handlers': [],
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

if config.get('saml2', 'log_file') != '':
    LOGGING['handlers']['file-saml2']['filename'] = config.get('saml2', 'log_file')
    LOGGING['loggers']['djangosaml2']['handlers'].append('file-saml2')

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

# LDAP
# Tested on FreeIPA.
#See also: https://pythonhosted.org/django-auth-ldap/
#AUTH_LDAP_SERVER_URI = "ldap://ldap.example.com/"
#AUTH_LDAP_BASE = "cn=accounts,dc=example,dc=com"
#AUTH_LDAP_BIND_DN = "uid=BINDUSERNAME," + AUTH_LDAP_USER_BASE
#AUTH_LDAP_BIND_PASSWORD = "BINDPASSWORD"

# LDAP user settings
#
#AUTH_LDAP_USER_BASE = "cn=users," + AUTH_LDAP_BASE
#AUTH_LDAP_USER_FILTER = "(uid=%(user)s)"
#AUTH_LDAP_USER_SEARCH = LDAPSearch(AUTH_LDAP_USER_BASE,
#            ldap.SCOPE_SUBTREE, AUTH_LDAP_USER_FILTER)

# Populate the Django user from the LDAP directory
#AUTH_LDAP_USER_ATTR_MAP = {
#    "first_name": "givenName",
#    "last_name": "sn",
#    "email": "mail"
#}

# LDAP group settings
#
#AUTH_LDAP_GROUP_BASE = "cn=groups," + AUTH_LDAP_BASE
#AUTH_LDAP_GROUP_FILTER = "(objectClass=groupOfNames)"
#AUTH_LDAP_GROUP_SEARCH = LDAPSearch(AUTH_LDAP_GROUP_BASE,
#    ldap.SCOPE_SUBTREE, AUTH_LDAP_GROUP_FILTER
#)
#AUTH_LDAP_GROUP_TYPE = GroupOfNamesType(name_attr="cn")

# Cache group memberships for an 10 mins to minimize LDAP traffic
#AUTH_LDAP_CACHE_GROUPS = True
#AUTH_LDAP_GROUP_CACHE_TIMEOUT = 600

# SAML2
SAML_CONFIG = {
    # full path to the xmlsec1 binary program
    'xmlsec_binary': '/usr/bin/xmlsec1',

    # your entity id, usually your subdomain plus the url to the metadata view
    'entityid': config.get('saml2', 'entity_id'),

    # directory with attribute mapping
    'attribute_map_dir': config.get('saml2', 'attribute_map_dir'),

    # this block states what services we provide
    'service': {
        # we are just a lonely SP
        'sp': {
            'endpoints': {
                # url and binding to the assertion consumer service view
                # do not change the binding or service name
                'assertion_consumer_service': [
                    (config.get('saml2', 'acs_url'), saml2.BINDING_HTTP_POST),
                ],
            },
            'allow_unsolicited': True,  # NOTE: This is the cornerstone! Never set to False

            # attributes that this project needs to identify a user
            'required_attributes': [
                'omanIDCivilNumber',
            ],

            # attributes that may be useful to have but not required
            'optional_attributes': [
                'omancardTitleFullNameEn',
                'omancardTitleFullNameAr',
            ],
        },
    },

    # where the remote metadata is stored
    'metadata': {
        'local': [
            config.get('saml2', 'idp_metadata_file'),
        ],
    },

    # set to 1 to output debugging information
    'debug': int(config.getboolean('saml2', 'debug')),

    # These following files are dummies
    # They are supposed to be valid, but are not really used.
    # They are only used to make PySAML2 happy.
    'key_file': config.get('saml2', 'key_file'),  # private part
    'cert_file': config.get('saml2', 'cert_file'),  # public part

    'only_use_keys_in_metadata': False,
    'allow_unknown_attributes': True,

    'accepted_time_diff': 120,
}

if config.get('saml2', 'idp_metadata_url') != '':
    SAML_CONFIG['metadata'].update({
        'remote': [
            {
                'url': config.get('saml2', 'idp_metadata_url'),
                'cert': config.get('saml2', 'idp_metadata_cert'),
            }
        ],
    })

SAML_DJANGO_USER_MAIN_ATTRIBUTE = 'civil_number'

SAML_ATTRIBUTE_MAPPING = {
    config.get('saml2', 'attribute_map_civil_number'): ('username', 'civil_number'),
    config.get('saml2', 'attribute_map_full_name'): ('full_name',),
    config.get('saml2', 'attribute_map_native_name'): ('native_name',),
}

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

# NodeConductor throttling settings for celery tasks
CELERY_TASK_THROTTLING = {
    'nodeconductor.iaas.tasks.openstack.openstack_provision_instance': {
        'concurrency': config.getint('celery', 'instance_provisioning_concurrency'),
    },
}

# NodeConductor internal configuration
# See also: http://nodeconductor.readthedocs.org/en/stable/guide/intro.html#id1
NODECONDUCTOR = {
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
            'postgresql-templateid': config.get('zabbix', 'postgresql_template_id'),
            'wordpress-templateid': config.get('zabbix', 'wordpress_template_id'),
            'zimbra-templateid': config.get('zabbix', 'zimbra_template_id'),
        }
    },
    'BILLING': {
        'backend': 'nodeconductor.billing.backend.whmcs.WHMCSAPI',
        'api_url': config.get('whmcs', 'api_url'),
        'username': config.get('whmcs', 'username'),
        'password': config.get('whmcs', 'password'),
        'currency_code': int(config.get('whmcs', 'currency_code')),
        'currency_name': config.get('whmcs', 'currency_name'),
        'openstack': {
            'invoice_meters': {
                # ceilometer meter name: (resource name, pricelist name, unit converter, unit)
                'cpu': ('CPU', 'cpu', 'hours'),
                'memory': ('Memory', 'ram_gb', 'GB/h'),
                'disk': ('Storage', 'storage_gb', 'GB/h'),
                'servers': ('Servers', 'server_num', 'units'),
                 # licenses
                'wordpress': ('WordPress', 'wordpress', 'hours'),
                'zimbra': ('Zimbra', 'zimbra', 'hours'),
                'postgresql': ('PostgreSQL', 'postgresql', 'hours'),

            }
        }
    },
    'ELASTICSEARCH': {
        'username': config.get('elasticsearch', 'username'),
        'password': config.get('elasticsearch', 'password'),
        'host': config.get('elasticsearch', 'host'),
        'port': config.get('elasticsearch', 'port'),
        'protocol': config.get('elasticsearch', 'protocol'),
    },



}

# Sentry integration
# See also: http://raven.readthedocs.org/en/latest/integrations/django.html#setup
if config.get('sentry', 'dsn') != '':
    INSTALLED_APPS = INSTALLED_APPS + ('raven.contrib.django.raven_compat',)
    RAVEN_CONFIG = {
        'dsn': config.get('sentry', 'dsn'),
    }

# optionally load extension configurations
plus_configuration = os.path.join(conf_dir, 'nodeconductor_plus.py')
if os.path.isfile(plus_configuration):
    execfile(plus_configuration)
