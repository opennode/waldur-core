from django.conf import settings

from nodeconductor.structure.models import ServiceSettings
from nodeconductor.jira.backend import JiraBackend, JiraBackendError


class SupportClient(object):
    """ NodeConductor support client via jira backend.
        Example settings configuration:

            NODECONDUCTOR['JIRA_SUPPORT'] = {
                'server': 'https://jira.example.com/',
                'username': 'alice@example.com',
                'password': 'password',
                'project': 'NST',
            }

        Jira configuration: https://confluence.nortal.com/pages/viewpage.action?title=Issue+tracker&spaceKey=ITACLOUD
    """

    ISSUE_TYPE = 'Support Request'
    REPORTER_FIELD = 'Original Reporter'

    def __new__(cls):
        base_config = settings.NODECONDUCTOR.get('JIRA_SUPPORT', {})
        dummy = base_config.get('dummy', False)

        if dummy:
            project = 'TST'
            jira_settings = ServiceSettings(dummy=True)
        else:
            try:
                project = base_config['project']
                jira_settings = ServiceSettings(
                    backend_url=base_config['server'],
                    username=base_config['username'],
                    password=base_config['password'],
                    type=ServiceSettings.Types.Jira)
            except (KeyError, AttributeError):
                raise JiraBackendError("Missed JIRA_SUPPORT settings or improperly configured")

        return JiraBackend(
            jira_settings,
            core_project=project,
            reporter_field=cls.REPORTER_FIELD,
            default_issue_type=cls.ISSUE_TYPE)
