Service Settings list
---------------------

To get a list of Service Settings, run GET against **/api/service-settings/** as an authenticated user.
Only settings owned by this user or shared settings will be listed.

Supported filters are:

- ?name=<text> - partial matching used for searching
- ?type=<type> - choices: OpenStack, DigitalOcean, Amazon, JIRA, GitLab, Oracle
- ?state=<state> - choices: New, Creation Scheduled, Creating, Sync Scheduled, Syncing, In Sync, Erred

Example response:

.. code-block:: http

    GET /api/service-settings/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "url": "http://example.com/api/service-settings/74e2adedf71c400e9fb5507644b47d67/",
            "uuid": "74e2adedf71c400e9fb5507644b47d67",
            "name": "GitLab",
            "type": "GitLab",
            "state": "In Sync",
            "error_message": "",
            "shared": false,
            "customer": "http://example.com/api/customers/d0d7fe366ee94e479e13d7a873644931/",
            "customer_name": "Zed Lebowski",
            "customer_native_name": "Zed Lebowski",
            "dummy": false
        }
    ]



Update Service Settings
-----------------------

To update service settings, issue a PUT or PATCH to **/api/service-settings/<uuid>/** as a customer owner.
You are allowed to change name and credentials only.

Example of a request:

.. code-block:: http

    PATCH /api/service-settings/9079705c17d64e6aa0af2e619b0e0702/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "username": "admin",
        "password": "new_secret"
    }
