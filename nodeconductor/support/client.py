from django.conf import settings

from nodeconductor.structure.models import ServiceSettings
from nodeconductor.jira.backend import JiraBackend, JiraBackendError


class SupportClient(object):
    """ NodeConductor support client via jira backend """

    ISSUE_TYPE = 'Support Request'
    REPORTER_FIELD = 'Original Reporter'

    def __new__(cls):
        base_config = settings.NODECONDUCTOR.get('JIRA_SUPPORT', {})

        try:
            project = base_config['project']
            jira_settings = ServiceSettings(
                backend_url=base_config['server'],
                username=base_config['username'],
                password=base_config['password'])
        except (KeyError, AttributeError):
            raise JiraBackendError("Missed JIRA_SUPPORT settings or improperly configured")

        return JiraBackend(
            jira_settings,
            core_project=project,
            reporter_field=cls.REPORTER_FIELD,
            default_issue_type=cls.ISSUE_TYPE)
