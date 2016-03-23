from __future__ import absolute_import

# Global import of all tasks from submodules.
# Required for proper work of celery autodiscover
# and adding all tasks to the registry.

from .backup import *
from .base import *
from .flavor import *
from .floating_ip import *
from .instance import *
from .network import *
from .security_group import *
from .tenant import *
from .volume import *

from celery import shared_task

@shared_task
def test(a, b):
    print a + b
    return a + b
