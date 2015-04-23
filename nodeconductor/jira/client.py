from __future__ import unicode_literals

import logging

from jira import JIRA, JIRAError

from django.conf import settings
from django.utils import six


logger = logging.getLogger(__name__)


class JiraClientError(Exception):
    pass


class JiraResource(object):
    """ Generic JIRA resource """

    def __init__(self, client):
        self.client = client


class JiraClient(object):
    """ NodeConductor interface to JIRA """

    class Issue(JiraResource):
        """ JIRA issues resource """

        class IssueQuerySet(object):
            """ Issues queryset acceptable by django paginator """

            def fetch_items(self, offset=0, limit=50):
                try:
                    result = self.query_func(
                        self.query_string,
                        fields=self.fields,
                        startAt=offset,
                        maxResults=limit,
                        json_result=True)
                except JIRAError as e:
                    logger.exception(
                        'Failed to perform issues search with query "%s"', self.query_string)
                    six.reraise(JiraClientError, e)

                self.total = result['total']
                self.limit = result['maxResults']
                self.offset = result['startAt']

                self.items = []
                for issue in result['issues']:
                    data = {'id': issue['key']}
                    data.update(issue['fields'])
                    self.items.append(data)

            def __init__(self, jira, query_string, fields=None):
                self.fields = fields
                self.query_func = jira.search_issues
                self.query_string = query_string
                self.fetch_items()

            def __len__(self):
                return self.total

            def __iter__(self):
                return self.items

            def __getitem__(self, val):
                self.fetch_items(offset=val.start, limit=val.stop - val.start)
                return self.items

        def create(self, summary, description='', reporter=None, assignee=None):
            if reporter:
                reporter = self.client.users.get(reporter)
            if assignee:
                assignee = self.client.users.get(assignee)

            try:
                issue = self.client.jira.create_issue(
                    summary=summary,
                    description=description,
                    project={'key': self.client.core_project},
                    issuetype={'name': 'Task'})

                if reporter:
                    issue.update(reporter={'name': reporter.name})
                if assignee:
                    self.client.jira.assign_issue(issue, assignee.key)

            except JIRAError as e:
                logger.exception('Failed to create issue with summary "%s"', summary)
                six.reraise(JiraClientError, e)

            return issue

        def list_by_user(self, username):
            query_string = "project = {} AND reporter = {}".format(
                self.client.core_project, username)

            return JiraClient.Issue.IssueQuerySet(
                self.client.jira, query_string, fields='summary,description')

    class User(JiraResource):
        """ JIRA users resource """

        def get(self, username):
            try:
                return self.client.jira.user(username)
            except JIRAError:
                raise JiraClientError("Unknown JIRA user %s" % username)

    def __init__(self, server=None, auth=None):
        self.core_project = None
        verify_ssl = True

        if not server:
            try:
                base_config = settings.NODECONDUCTOR['JIRA']
                server = base_config['server']
            except (KeyError, AttributeError):
                raise JiraClientError(
                    "Missed JIRA server. It must be supplied explicitly or defined "
                    "within settings.NODECONDUCTOR.JIRA")

            try:
                self.core_project = base_config['project']
            except KeyError:
                raise JiraClientError(
                    "Missed JIRA project key. Please define it as "
                    "settings.NODECONDUCTOR.JIRA['project']")

            if not auth:
                auth = base_config.get('auth')

            if 'verify' in base_config:
                verify_ssl = base_config['verify']

        self.jira = JIRA({'server': server, 'verify': verify_ssl}, basic_auth=auth, validate=False)
        self.users = self.User(self)
        self.issues = self.Issue(self)
