from __future__ import unicode_literals

from jira import JIRA
from django.conf import settings


class JiraClientError(Exception):
    pass


class JiraClient(object):

    def __init__(self, server=None, auth=None):
        if not server:
            try:
                base_config = settings.NODECONDUCTOR['JIRA']
                server = base_config['server']
            except:
                raise JiraClientError(
                    "Missed jira server. It must be supplied explicitly or defined "
                    "within settings.NODECONDUCTOR.JIRA")

            if not auth:
                auth = base_config.get('auth')

        self.client = JIRA({'server': server}, basic_auth=auth)
