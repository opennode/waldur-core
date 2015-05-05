JIRA issues list
----------------

To get a list of JIRA issues, run GET against **/api/issues/** as an authenticated user.
Only issues reported to this user will be listed. Users match is made by username.

Supported filters are:

- ?search=<text> - full text search for issues by 'summary', 'description' or 'comments'

JIRA issue comments
-------------------

To get a list of JIRA issue comments, run GET against **/api/issues/<key>/comments/**.

To add a new comment, issue a POST to **/api/issues/<key>/comments/**.
Example of a request:

.. code-block:: http

    POST /api/issues/NC-1/comments/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token 94c7ff222e2021b0ed25291b67014e1aa5c1da51
    Host: example.com

    {
        "body": "Lorem ipsum dolor sit amet, consectetuer adipiscing elit.",
    }
