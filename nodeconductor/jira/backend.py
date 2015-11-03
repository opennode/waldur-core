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


class JiraBackend(object):

    def __init__(self, settings, **kwargs):
        self.backend = JiraRealBackend(settings, **kwargs)

    def __getattr__(self, name):
        return getattr(self.backend, name)


class JiraBaseBackend(ServiceBackend):

    def sync(self):
        pass


class JiraRealBackend(JiraBaseBackend):
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

    def __init__(self, settings, core_project=None, reporter_field=None, default_issue_type='Task'):
        self.settings = settings
        self.core_project = core_project
        self.reporter_field = reporter_field
        self.default_issue_type = default_issue_type

        if settings.dummy:
            self.jira = JiraDummyClient()
        else:
            self.jira = JIRA(
                {'server': settings.backend_url, 'verify': False},
                basic_auth=(settings.username, settings.password), validate=False)

        if self.reporter_field:
            try:
                self.reporter_field_id = next(
                    f['id'] for f in self.jira.fields() if self.reporter_field in f['clauseNames'])
            except StopIteration:
                raise JiraBackendError("Can't custom field %s" % self.reporter_field)

        self.users = self.User(self)
        self.issues = self.Issue(self)
        self.comments = self.Comment(self)


class JiraDummyClient(object):
    """ Dummy JIRA API manager """

    class DataSet(object):
        USERS = (
            {'key': 'alice', 'displayName': 'Alice', 'emailAddress': 'alice@example.com'},
            {'key': 'bob', 'displayName': 'Bob', 'emailAddress': 'bob@example.com'},
        )

        FIELDS = [
            {'clauseNames': ['issuetype', 'type'],
                'custom': False,
                'id': 'issuetype',
                'name': 'Issue Type',
                'navigable': True,
                'orderable': True,
                'schema': {'system': 'issuetype', 'type': 'issuetype'},
                'searchable': True},
            {'clauseNames': ['project'],
                'custom': False,
                'id': 'project',
                'name': 'Project',
                'navigable': True,
                'orderable': False,
                'schema': {'system': 'project', 'type': 'project'},
                'searchable': True},
            {'clauseNames': ['description'],
                'custom': False,
                'id': 'description',
                'name': 'Description',
                'navigable': True,
                'orderable': True,
                'schema': {'system': 'description', 'type': 'string'},
                'searchable': True},
            {'clauseNames': ['summary'],
                'custom': False,
                'id': 'summary',
                'name': 'Summary',
                'navigable': True,
                'orderable': True,
                'schema': {'system': 'summary', 'type': 'string'},
                'searchable': True},
            {'clauseNames': ['cf[10000]', 'Original Reporter'],
                'custom': True,
                'id': 'customfield_10000',
                'name': 'Original Reporter',
                'navigable': True,
                'orderable': True,
                'schema': {'custom': 'com.atlassian.jira.plugin.system.customfieldtypes:textfield',
                           'customId': 10000,
                           'type': 'string'},
                'searchable': True},
        ]

        ISSUES = (
            {
                'key': 'TST-1',
                'fields': {'summary': 'Bake a cake', 'description': 'Angel food please'},
                'created': now(),
            },
            {
                'key': 'TST-2',
                'fields': {'summary': 'Pet a cat', 'description': None, 'assignee': 'bob'},
                'created': now(),
            },
            {
                'key': 'TST-3',
                'fields': {
                    'summary': 'Take a nap',
                    'description': None,
                    'comments': [
                        {'author': 'bob', 'body': 'Just a reminder -- this is a high priority task.', 'created': now()},
                        {'author': 'alice', 'body': 'sweet dreams ^_^', 'created': now()},
                    ],
                },
                'created': now(),
            },
        )

    class ResultSet(list):
        total = 0

        def __getslice__(self, start, stop):
            data = self.__class__(list.__getslice__(self, start, stop))
            data.total = len(self)
            return data

    class Resource(object):
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def __repr__(self):
            reprkeys = sorted(k for k in self.__dict__.keys())
            info = ", ".join("%s='%s'" % (k, getattr(self, k)) for k in reprkeys if not k.startswith('_'))
            return "<JIRA {}: {}>".format(self.__class__.__name__, info)

    class PersistentResource(Resource):
        def __init__(self, **kwargs):
            super(JiraDummyClient.PersistentResource, self).__init__(**kwargs)
            key = "%ss" % self.__class__.__name__.lower()
            DATA.setdefault(key, set())
            DATA[key].add(self)

        def __hash__(self):
            return abs(hash(self.key)) % (10 ** 8)

        def __eq__(self, other):
            return self.key == other.key

    class Issue(PersistentResource):
        def update(self, reporter=()):
            self.fields.reporter = JiraDummyClient().user(reporter['name'])

    class Comment(Resource):
        pass

    class User(PersistentResource):
        pass

    def __init__(self):
        users = {data['key']: self.User(name=data['key'], **data) for data in self.DataSet.USERS}
        self._current_user = users.get('alice')
        for data in self.DataSet.ISSUES:
            issue = self.Issue(**data)

            comments = []
            comments_data = data['fields'].get('comments', [])
            for data in comments_data:
                comment = self.Comment(**data)
                comment.author = users[data.get('author')]
                comments.append(comment)

            issue.fields = self.Resource(**issue.fields)
            issue.fields.comments = comments
            issue.fields.reporter = self._current_user
            if hasattr(issue.fields, 'assignee'):
                issue.fields.assignee = users.get(issue.fields.assignee)

        self._users = DATA.get('users', [])
        self._issues = DATA.get('issues', [])

    def current_user(self):
        return self._current_user.emailAddress

    def user(self, user_key):
        try:
            return next(u for u in self._users if u.key == user_key)
        except StopIteration:
            return self._current_user

    def issue(self, issue_key):
        try:
            return next(i for i in self._issues if i.key == issue_key)
        except StopIteration:
            raise JIRAError("Issue %s not found" % issue_key)

    def assign_issue(self, issue, user_key):
        issue.assignee = self.user(user_key)

    def create_issue(self, **kwargs):
        fields = kwargs.get('fields') or kwargs
        fields['reporter'] = 'admin'
        fields['comments'] = []
        issue = self.Issue(
            key='TST-{}'.format(len(self._issues) + 1),
            created=datetime.datetime.now(),
            fields=self.Resource(**fields))
        return issue

    def search_issues(self, query, startAt=0, maxResults=50, **kwargs):
        term = None
        for param in query.split(' AND '):
            if param.startswith('text'):
                term = param.replace('text ~ ', '').replace(r'\\', '').strip('"').lower()
        if term:
            results = []
            for issue in self._issues:
                text = ' '.join([
                    getattr(issue.fields, field) or ''
                    for field in ('summary', 'description')])
                if term in text.lower():
                    results.append(issue)
                    continue
                for comment in issue.fields.comments:
                    if term in comment.body.lower():
                        results.append(issue)
                        break
        else:
            results = self._issues

        return self.ResultSet(results)[startAt:startAt + maxResults]

    def fields(self):
        return self.DataSet.FIELDS

    def comments(self, issue_key):
        return self.issue(issue_key).fields.comments

    def add_comment(self, issue_key, body):
        comment = self.Comment(
            author=self._current_user, created=datetime.datetime.now(), body=body)
        self.issue(issue_key).fields.comments.append(comment)
        return comment
