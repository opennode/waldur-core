from __future__ import absolute_import

# Global import of all tasks from submodules.
# Required for proper work of celery autodiscover
# and adding all tasks to the registry.

from .backup import *
from .base import *
from .celerybeat import *
from .flavor import *
from .floating_ip import *
from .instance import *
from .security_group import *
from .volume import *
