from __future__ import unicode_literals

import re
import random
import logging
import datetime
import threading

from jira import JIRA, JIRAError

from django.utils import six

from nodeconductor.structure import ServiceBackend, ServiceBackendError


now = lambda: datetime.datetime.now() - datetime.timedelta(minutes=random.randint(0, 60))
DATA = threading.local().jira_data = {}
logger = logging.getLogger(__name__)


class JiraBackendError(ServiceBackendError):
    pass


class JiraBaseBackend(ServiceBackend):

    def __init__(self, settings, core_project=None, reporter_field=None, default_issue_type='Task'):
        self.settings = settings
        self.core_project = core_project
        self.reporter_field = reporter_field
        self.default_issue_type = default_issue_type

        self.jira = JIRA(
            server=settings.backend_url,
            options={'verify': False},
            basic_auth=(settings.username, settings.password),
            validate=False)

        if self.reporter_field:
            try:
                self.reporter_field_id = next(
                    f['id'] for f in self.jira.fields() if self.reporter_field in f['clauseNames'])
            except StopIteration:
                raise JiraBackendError("Can't custom field %s" % self.reporter_field)


class JiraBackend(JiraBaseBackend):
    """ NodeConductor interface to JIRA """

    class Resource(object):
        """ Generic JIRA resource """

        def __init__(self, manager):
            self.manager = manager

    class Issue(Resource):
        """ JIRA issues resource """

        class IssueQuerySet(object):
            """ Issues queryset acceptable by django paginator """

            def filter(self, term):
                if term:
                    escaped_term = re.sub(r'([\^~*?\\:\(\)\[\]\{\}|!#&"+-])', r'\\\\\1', term)
                    self.query_string = self.base_query_string + ' AND text ~ "%s"' % escaped_term
                return self

            def _fetch_items(self, offset=0, limit=1, force=False):
                # Default limit is 1 because this extra query required
                # only to determine the total number of items
                if hasattr(self, 'items') and not force:
                    return self.items

                try:
                    self.items = self.query_func(
                        self.query_string,
                        fields=self.fields,
                        startAt=offset,
                        maxResults=limit)
                except JIRAError as e:
                    logger.exception(
                        'Failed to perform issues search with query "%s"', self.query_string)
                    six.reraise(JiraBackendError, e)

                return self.items

            def __init__(self, jira, query_string, fields=None):
                self.fields = fields
                self.query_func = jira.search_issues
                self.query_string = self.base_query_string = query_string

            def __len__(self):
                return self._fetch_items().total

            def __iter__(self):
                return self._fetch_items()

            def __getitem__(self, val):
                return self._fetch_items(offset=val.start, limit=val.stop - val.start, force=True)

        def create(self, summary, description='', reporter='', assignee=None):
            args = {
                'summary': summary,
                'description': description,
                'project': {'key': self.manager.core_project},
                'issuetype': {'name': self.manager.default_issue_type},
            }

            # Validate reporter & assignee before actual issue creation
            if assignee:
                assignee = self.manager.users.get(assignee)
            if self.manager.reporter_field:
                args[self.manager.reporter_field_id] = reporter
            elif reporter:
                reporter = self.manager.users.get(reporter)

            try:
                issue = self.manager.jira.create_issue(fields=args)

                if reporter and not self.manager.reporter_field:
                    issue.update(reporter={'name': reporter.name})
                if assignee:
                    self.manager.jira.assign_issue(issue, assignee.key)

            except JIRAError as e:
                logger.exception('Failed to create issue with summary "%s"', summary)
                six.reraise(JiraBackendError, e)

            return issue

        def get_by_user(self, username, user_key):
            try:
                issue = self.manager.jira.issue(user_key)
            except JIRAError:
                raise JiraBackendError("Can't find issue %s" % user_key)

            if self.manager.reporter_field:
                is_owner = getattr(issue.fields, self.manager.reporter_field_id) == username
            else:
                reporter = self.manager.users.get(username)
                is_owner = issue.fields.reporter.key == reporter.key

            if not is_owner:
                raise JiraBackendError("Access denied to issue %s for user %s" % (user_key, username))

            return issue

        def list_by_user(self, username):
            if self.manager.reporter_field:
                query_string = "project = {} AND '{}' ~ '{}'".format(
                    self.manager.core_project, self.manager.reporter_field, username)
            else:
                query_string = "project = {} AND reporter = {}".format(
                    self.manager.core_project, username)
            query_string += " order by updated desc"

            return self.IssueQuerySet(self.manager.jira, query_string)

    class Comment(Resource):
        """ JIRA issue comments resource """

        def list(self, issue_key):
            try:
                return self.manager.jira.comments(issue_key)
            except JIRAError as e:
                logger.exception(
                    'Failed to perform comments search for issue %s', issue_key)
                six.reraise(JiraBackendError, e)

        def create(self, issue_key, comment):
            return self.manager.jira.add_comment(issue_key, comment)

    class User(Resource):
        """ JIRA users resource """

        def get(self, username):
            try:
                return self.manager.jira.user(username)
            except JIRAError:
                raise JiraBackendError("Unknown JIRA user %s" % username)

    def __init__(self, *args, **kwargs):
        super(JiraBackend, self).__init__(*args, **kwargs)

        self.users = self.User(self)
        self.issues = self.Issue(self)
        self.comments = self.Comment(self)
