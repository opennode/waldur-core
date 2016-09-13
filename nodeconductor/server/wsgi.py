"""
WSGI config for nodeconductor project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
import nodeconductor  # pre-load NC monkey-patching methods
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nodeconductor.server.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
