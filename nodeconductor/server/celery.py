from __future__ import absolute_import

import logging.config
import os

from celery import Celery
from celery.signals import setup_logging
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nodeconductor.server.settings')  # XXX:

app = Celery('nodeconductor')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


# Taken from https://github.com/celery/celery/issues/1867#issuecomment-34867070
@setup_logging.connect
def setup_logging(loglevel, logfile, format, colorize, **kwargs):
    from django.conf import settings

    logging.config.dictConfig(settings.LOGGING)
