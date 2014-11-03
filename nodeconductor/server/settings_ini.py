# Django settings for nodeconductor project
from nodeconductor.server.base_settings import *

import os
import saml2

from ConfigParser import RawConfigParser

conf_dir = os.path.join(os.path.expanduser('~'), '.nodeconductor')

config = RawConfigParser()
config.read(os.path.join(conf_dir, 'settings.ini'))

# If these sections and/or options are not set, these values are used as defaults
config_defaults = {
    'global': {
        'db_backend': 'sqlite3',
        'debug': 'false',
        'secret_key': '',
        'static_root': os.path.join(conf_dir, 'static'),
        'template_debug': 'false',
    },
    'events': {
        'log_file': '',  # empty to disable
        'log_level': 'INFO',
        'syslog': 'false',
    },
    'logging': {
        'log_file': '',  # empty to disable
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
    'saml2': {
        'acs_url': '',
        'attribute_map_dir': os.path.join(conf_dir, 'attribute-maps'),
        'cert_file': os.path.join(conf_dir, 'dummy.crt'),
        'debug': 'false',
        'entity_id': 'saml-sp2',
        'key_file': os.path.join(conf_dir, 'dummy.pem'),
        'log_file': '',  # empty to disable
        'log_level': 'INFO',
        'metadata_cert': '',
        'metadata_file': os.path.join(conf_dir, 'metadata.xml'),
        'metadata_url': '',
    },
    'sqlite3': {
        'path': os.path.join(conf_dir, 'db.sqlite3'),
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
TEMPLATE_DEBUG = config.getboolean('global', 'template_debug')

ALLOWED_HOSTS = ['*']

#
# Application definition
#

# Database
# See also: https://docs.djangoproject.com/en/1.6/ref/settings/#databases

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
    # Example: install MySQL-python in RHEL6, CentOS 6.x etc.:
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

# Logging
# See also: https://docs.djangoproject.com/en/1.6/ref/settings/#logging

LOGGING = {
    'version': 1,
    'formatters': {
        'request_format': {
            'format': '%(remote_addr)s %(username)s "%(request_method)s '
            '%(path_info)s %(server_protocol)s" %(http_user_agent)s '
            '%(message)s %(asctime)s',
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
            'address': '/dev/log',
            'class': 'logging.handlers.SysLogHandler',
            'filters': ['request'],
            'formatter': 'request_format',
            'level': config.get('logging', 'log_level').upper(),
        },
        'syslog-event': {
            'address': '/dev/log',
            'class': 'logging.handlers.SysLogHandler',
            'filters': ['request'],
            'formatter': 'request_format',
            'level': config.get('events', 'log_level').upper(),
        },
    },
    'loggers': {
        'django': {
            'handlers': [],
            'level': config.get('logging', 'log_level').upper(),
            'propagate': True,
        },
        # NodeConductor events
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
    LOGGING['loggers']['django']['handlers'].append('syslog')

if config.get('events', 'log_file') != '':
    LOGGING['handlers']['file-event']['filename'] = config.get('events', 'log_file')
    LOGGING['loggers']['nodeconductor']['handlers'].append('file-event')

if config.getboolean('events', 'syslog'):
    LOGGING['loggers']['nodeconductor']['handlers'].append('syslog-event')

if config.get('saml2', 'log_file') != '':
    LOGGING['handlers']['file-saml2']['filename'] = config.get('saml2', 'log_file')
    LOGGING['loggers']['nodeconductor.core.views']['handlers'].append('file-saml2')

# Static files
# See also: https://docs.djangoproject.com/en/1.6/ref/settings/#static-files

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
            config.get('saml2', 'metadata_file'),
        ],
    },

    # set to 1 to output debugging information
    'debug': int(config.getboolean('saml2', 'debug')),

    # These following files are dummies
    # They are supposed to be valid, but are not really used.
    # They are only used to make PySAML2 happy.
    'key_file': '/path/to/key.pem',  # private part
    'cert_file': '/path/to/certificate.crt',  # public part

    'accepted_time_diff': 120,
}

if config.get('saml2', 'metadata_url') != '':
    SAML_CONFIG['metadata'].update({
        'remote': [
            {
                'url': config.get('saml2', 'metadata_url'),
                'cert': config.get('saml2', 'metadata_cert'),
            }
        ],
    })

SAML_DJANGO_USER_MAIN_ATTRIBUTE = 'civil_number'

SAML_ATTRIBUTE_MAPPING = {
    'Civil number': ('username', 'civil_number'),
    'omancardTitleFullNameEn': ('full_name', ),
    'omancardTitleFullNameAr': ('native_name', ),
}

# Celery
# See also: http://docs.celeryproject.org/en/latest/getting-started/brokers/index.html#broker-instructions
# See also: http://docs.celeryproject.org/en/latest/configuration.html#broker-url
BROKER_URL = 'redis://localhost'

# See also: http://docs.celeryproject.org/en/latest/configuration.html#std:setting-CELERY_RESULT_BACKEND
CELERY_RESULT_BACKEND = 'redis://localhost'

# See also: http://docs.celeryproject.org/en/latest/configuration.html#celery-accept-content
CELERY_ACCEPT_CONTENT = ['json']
