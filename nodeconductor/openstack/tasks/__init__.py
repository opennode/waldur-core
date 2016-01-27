from __future__ import absolute_import

# Global import of all tasks from submodules.
# Required for proper work of celery autodiscover
# and adding all tasks to the registry.

from .backup import *
from .flavor import *
from .floating_ip import *
from .instance import *
from .network import *
from .security_group import *
from .tenant import *
from .volume import *
