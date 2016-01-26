Introduction
------------

The backups can be created either manually or by setting a schedule for regular automatic backups.

Backup
------

To create a backup, issue the following POST request:

.. code-block:: http

    POST /api/openstack-backups/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "instance": "http://example.com/api/openstack-instances/a04a26e46def4724a0841abcb81926ac/",
        "description": "a new manual backup"
    }

On creation of backup it's projected size is validated against a remaining storage quota.

Example of a created backup representation:

.. code-block:: http

    GET /api/openstack-backups/7441df421d5443118af257da0f719533/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "url": "http://example.com/api/openstack-backups/7441df421d5443118af257da0f719533/",
        "instance": "http://example.com/api/openstack-instances/a04a26e46def4724a0841abcb81926ac/",
        "description": "a new manual backup",
        "created_at": "2014-10-19T20:43:37.370Z",
        "kept_until": null,
        "state": "Backing up",
        "backup_schedule": "http://example.com/api/openstack-backup-schedules/075c3525b9af42e08f54c3ccf87e998a/"
    }

Please note, that backups can be both manual and automatic, triggered by the schedule.
In the first case, **backup_schedule** field will be **null**, in the latter - contain a link to the schedule.

Backup has a state, currently supported states are:

- Ready
- Backing up
- Restoring
- Deleting
- Erred

You can filter backup by description or instance field, which should match object URL.
It is useful when one resource has several backups and you want to get all backups related to this resource.

Backup actions
--------------

Created backups support several operations. Only users with write access to backup source are allowed to perform these
operations:

- **/api/openstack-backup/<backup_uuid>/restore/** - restore a specified backup. Restoring a backup can take user input.
  Restoration is available only for backups in state ``READY``. If backup is not ready, status code of the response
  will be **409 CONFLICT**.
  Supported inputs for VM Instance:

  - image - URL to a image used for restoration. Mandatory.
  - flavor - URL to a flavor used for restoration. Mandatory.
  - name - Name of the restored VM. Optional (equals to the name of the original VM by default).

- **/api/openstack-backup/<backup_uuid>/delete/** - delete a specified backup

If a backup is in a state that prohibits this operation, it will be returned in error message of the response.

Backup schedules
----------------

To perform backups on a regular basis, it is possible to define a backup schedule. Example of a request:

.. code-block:: http

    POST /api/openstack-backup-schedules/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "instance": "http://example.com/api/openstack-instances/430abd492a384f9bbce5f6b999ac766c/",
        "description": "schedule description",
        "retention_time": 0,
        "timezone": "Europe/London",
        "maximal_number_of_backups": 10,
        "schedule": "1 1 1 1 1",
        "is_active": true
    }

For schedule to work, it should be activated - it's flag is_active set to true. If it's not, it won't be used
for triggering the next backups. Schedule will be deactivated if backup fails.

- **retention time** is a duration in days during which backup is preserved.
- **maximal_number_of_backups** is a maximal number of active backups connected to this schedule.
- **schedule** is a backup schedule defined in a cron format.
- **timezone** is used for calculating next run of the backup (optional).

Activating/deactivating a schedule
----------------------------------

A schedule can be it two states: active or not. Non-active states are not used for scheduling the new tasks.
Only users with write access to backup schedule source can activate or deactivate schedule.

To activate a backup schedule, issue POST request to **/api/openstack-backup-schedules/<UUID>/activate/**. Note that
if a schedule is already active, this will result in **409 CONFLICT** code.

To deactivate a backup schedule, issue POST request to **/api/openstack-backup-schedules/<UUID>/deactivate/**. Note that
if a schedule was already deactivated, this will result in **409 CONFLICT** code.
