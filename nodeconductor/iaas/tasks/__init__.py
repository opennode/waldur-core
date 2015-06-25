from __future__ import absolute_import

# Global import of all tasks from submodules.
# Required for proper work of celery autodiscover
# and adding all tasks to the registry.

from .flavors import *
from .iaas import *
from .instance import *
from .openstack import *
from .security_groups import *
from .services import *
from .zabbix import *
