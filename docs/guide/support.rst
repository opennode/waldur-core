Issue tracker
-------------

NodeConductor can integrate with Atlassian JIRA to provide support to
the end-users. To enable integration, JIRA settings should be added, for example:

.. code-block:: python

    NODECONDUCTOR['JIRA_SUPPORT'] = {
        'server': 'https://jira.example.com/',
        'username': 'alice@example.com',
        'password': 'password',
        'project': 'NST',
    }

Expected structure for the JIRA project is as follows:

- Existing issue type: Support Request (must be default issue type for the project)
- Custom fields: 

  * Impact, type: Text Field (single line)
  * Original Reporter, type: Text Field (single line)

Expected permissions:

+-------------------+------------------+
| Permission        | Permission code  |
+===================+==================+
| Add Comments      | COMMENT_ISSUE    |
+-------------------+------------------+
| Edit Own Comments | COMMENT_EDIT_OWN | 
+-------------------+------------------+
| Browse Projects   | BROWSE           |
+-------------------+------------------+
