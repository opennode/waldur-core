# TODO: Move all this settings to separate application G-Cloud assembly.
""" Configurations for G-Cloud specific actions. """

# Name of shared settings that will be used for creating default hosts
SHARED_ZABBIX_SETTINGS_NAME = 'Zabbix'

# This templates should be added to each host that corresponds to any OpenStack
DEFAULT_HOST_TEMPLATES = ['Template NodeConductor Instance']

# Map instance tag to zabbix templates names
ADDITIONAL_HOST_TEMPLATES = {
    'license-application:zimbra': ['Template PaaS App Zimbra'],
    'license-application:wordpress': ['Template PaaS App Wordpress'],
    'license-application:postgresql': ['Template PaaS App PostgreSQL'],
    'license-application:sugar': ['Template SaaS App SugarCRM'],
    'license-application:zabbix': ['Template Paas App Zabbix'],
}

# trigger name that will be used for be used in IT service for SLA calculation
DEFAULT_SLA_TRIGGER_NAME = 'Missing data about the VM'

# <key> - OpenStack instance tag name.
# <value> - name of the trigger that will be used for SLA calculation if instance has <key> in tags.
SLA_TRIGGER_NAMES = {
    'license-application:zimbra': 'Zimbra is not available',
    'license-application:wordpress': 'Wordpress is not available',
    'license-application:postgresql': 'PostgreSQL is not available',
    'license-application:sugar': 'SugarCRM is not available',
    'license-application:zabbix': 'Zabbix is not available',
}

# Group for all hosts
HOST_GROUP_NAME = 'NodeConductor'

# SLA
AGREED_SLA = 95
