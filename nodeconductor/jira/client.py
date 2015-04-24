from __future__ import unicode_literals

import re
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

            def filter(self, term):
                if term:
                    escaped_term = re.sub(r'([\^~*?\\:\(\)\[\]\{\}|!#&"+-])', r'\\\\\1', term)
                    self.query_string = self.base_query_string + ' AND text ~ "%s"' % escaped_term
                return self

            def _fetch_items(self, offset=0, limit=1):
                # Default limit is 1 because this extra query required
                # only to determine the total number of items
                try:
                    self.items = self.query_func(
                        self.query_string,
                        fields=self.fields,
                        startAt=offset,
                        maxResults=limit)
                except JIRAError as e:
                    logger.exception(
                        'Failed to perform issues search with query "%s"', self.query_string)
                    six.reraise(JiraClientError, e)

            def __init__(self, jira, query_string, fields=None):
                self.fields = fields
                self.query_func = jira.search_issues
                self.query_string = self.base_query_string = query_string

            def __len__(self):
                if not hasattr(self, 'items'):
                    self._fetch_items()
                return self.items.total

            def __iter__(self):
                if not hasattr(self, 'items'):
                    self._fetch_items()
                return self.items

            def __getitem__(self, val):
                self._fetch_items(offset=val.start, limit=val.stop - val.start)
                return self.items

        def create(self, summary, description='', reporter=None, assignee=None):
            # Validate reporter & assignee before actual issue creation
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

        def get_by_user(self, username, user_key):
            reporter = self.client.users.get(username)

            try:
                issue = self.client.jira.issue(user_key)
            except JIRAError:
                raise JiraClientError("Can't find issue %s" % user_key)

            if issue.fields.reporter.key != reporter.key:
                raise JiraClientError("Access denied to issue %s for user %s" % (user_key, username))

            return issue

        def list_by_user(self, username):
            query_string = "project = {} AND reporter = {}".format(
                self.client.core_project, username)

            return self.IssueQuerySet(self.client.jira, query_string)

    class Comment(JiraResource):
        """ JIRA issue comments resource """

        def list(self, issue_key):
            return self.client.jira.comments(issue_key)

        def create(self, issue_key, comment):
            return self.client.jira.add_comment(issue_key, comment)

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
        self.comments = self.Comment(self)
