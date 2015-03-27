from __future__ import absolute_import

# Global import of all tasks from submodules.
# Required for proper work of celery autodiscover
# and adding all tasks to the registry.

from .iaas import *
from .zabbix import *
from .instance import *
from .flavors import *
from .openstack import *
