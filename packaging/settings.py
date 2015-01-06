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
        'secret_key': '',
        'static_root': os.path.join(data_dir, 'static'),
        'template_debug': 'false',
    },
    'celery': {
        'broker_url': 'redis://localhost',
        'result_backend_url': 'redis://localhost',
    },
    'events': {
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
        'password': '',
        'tenant_name': '',
        'username': '',
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
    'zabbix': {
        'db_host': '',  # empty to disable Zabbix database access
        'db_name': 'zabbix',
        'db_password': 'nodeconductor',
        'db_port': '3306',
        'db_user': 'nodeconductor',
        'host_group_id': '',
        'host_template_id': '',
        'password': '',
        'server_url': '',
        'username': '',
    }
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
    'disable_existing_loggers': False, # Fixes Celery beat logging
    'formatters': {
        'request_format': {
            'format': '%(asctime)s %(remote_addr)s %(username)s "%(request_method)s '
            '%(path_info)s %(server_protocol)s" %(http_user_agent)s '
            '%(message)s',
        },
    },
    'filters': {
        # Populate each log entry with HTTP request information
        'request': {
            '()': 'django_requestlogging.logging_filters.RequestFilter',
        },
        # Filter out only event (user-facing) logs
        'event': {
            '()': 'nodeconductor.core.log.EventLogFilter',
        }
    },
    'handlers': {
        # Logging to file
        # See also: https://docs.python.org/2/library/logging.handlers.html#watchedfilehandler
        'file': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': '/dev/null',
            'filters': ['request'],
            'formatter': 'request_format',
            'level': config.get('logging', 'log_level').upper(),
        },
        'file-event': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': '/dev/null',
            'filters': ['request', 'event'],
            'formatter': 'request_format',
            'level': config.get('events', 'log_level').upper(),
        },
        'file-saml2': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': '/dev/null',
            'filters': ['request'],
            'formatter': 'request_format',
            'level': config.get('saml2', 'log_level').upper(),
        },
        # Logging to syslog
        # See also: https://docs.python.org/2/library/logging.handlers.html#sysloghandler
        'syslog': {
            'class': 'logging.handlers.SysLogHandler',
            'filters': ['request'],
            'formatter': 'request_format',
            'level': config.get('logging', 'log_level').upper(),
        },
        'syslog-event': {
            'class': 'logging.handlers.SysLogHandler',
            'filters': ['request'],
            'formatter': 'request_format',
            'level': config.get('events', 'log_level').upper(),
        },
        # Logging to logserver
        'tcp-event': {
            'class': 'nodeconductor.core.log.TCPEventHandler',
            'filters': ['event'],
            'level': config.get('events', 'log_level').upper(),
        },
    },
    'loggers': {
        'django': {
            'handlers': [],
            'level': config.get('logging', 'log_level').upper(),
            'propagate': True,
        },
        'nodeconductor': {
            'handlers': [],
            'level': config.get('events', 'log_level').upper(),
            'propagate': True,
        },
        'nodeconductor.core.views': {
            'handlers': [],
            'level': config.get('saml2', 'log_level').upper(),
            'propagate': True,
        },
    },
}

if config.get('logging', 'log_file') != '':
    LOGGING['handlers']['file']['filename'] = config.get('logging', 'log_file')
    LOGGING['loggers']['django']['handlers'].append('file')

if config.getboolean('logging', 'syslog'):
    LOGGING['handlers']['syslog']['address'] = '/dev/log'
    LOGGING['loggers']['django']['handlers'].append('syslog')

if config.get('events', 'log_file') != '':
    LOGGING['handlers']['file-event']['filename'] = config.get('events', 'log_file')
    LOGGING['loggers']['nodeconductor']['handlers'].append('file-event')

if config.get('events', 'logserver_host') != '':
    LOGGING['handlers']['tcp-event']['host'] = config.get('events', 'logserver_host')
    LOGGING['handlers']['tcp-event']['port'] = config.get('events', 'logserver_port')
    LOGGING['loggers']['nodeconductor']['handlers'].append('tcp-event')

if config.getboolean('events', 'syslog'):
    LOGGING['handlers']['syslog-event']['address'] = '/dev/log'
    LOGGING['loggers']['nodeconductor']['handlers'].append('syslog-event')

if config.get('saml2', 'log_file') != '':
    LOGGING['handlers']['file-saml2']['filename'] = config.get('saml2', 'log_file')
    LOGGING['loggers']['nodeconductor.core.views']['handlers'].append('file-saml2')

# Static files
# See also: https://docs.djangoproject.com/en/1.7/ref/settings/#static-files

STATIC_ROOT = config.get('global', 'static_root')

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
for key in ['metadata_cert', 'metadata_file', 'metadata_url']:
    if config.has_option('saml2', key) and config.get('saml2', key) != '' and config.get('saml2', 'idp_' + key) == '':
        warnings.warn(
           "Config option %s is deprectaed and will be removed in NodeConductor 0.23; use idp_%s instead" % (key, key),
            PendingDeprecationWarning)  # TODO-0.22: PendingDeprecationWarning -> DeprecationWarning
        configs.set('saml2', 'idp_' + key, config.get(key))

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

NODECONDUCTOR = {
    'OPENSTACK_CREDENTIALS': (
        {
            'auth_url': config.get('openstack', 'auth_url'),
            'username': config.get('openstack', 'username'),
            'password': config.get('openstack', 'password'),
            'tenant_name': config.get('openstack', 'tenant_name'),
        },
        {
            'auth_url': 'http://localhost:55000',
            'username': 'nodeconductor',
            'password': 'nodeconductor',
            'tenant_name': 'test',
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
        }
    }
}

# Sentry integration
# See also: http://raven.readthedocs.org/en/latest/integrations/django.html#setup
if config.get('sentry', 'dsn') != '':
    INSTALLED_APPS = INSTALLED_APPS + ('raven.contrib.django.raven_compat',)
    RAVEN_CONFIG = {
        'dsn': config.get('sentry', 'dsn'),
    }

