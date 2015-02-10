CHANGELOG
=========

Coming in the next release
--------------------------

(Fixes/changes that are in develop branch.)
- Dropped backup quota. Rely on storage quota only.

Release 0.33.0
--------------

- Improved user key propagation speed to the backend.
- Refactored OpenStack backups to use volumes only.

Release 0.32.0
--------------

- Staff users are now listed to staff users only.
- Bugfixes

Release 0.31.0
--------------

- Bugfixes

Release 0.30.0
--------------

- Bugfixes

Release 0.29.0
--------------

- Bugfixes

Release 0.28.0
--------------

- Scheduled backups are now run as Celery tasks.
- Changed quota usage to be re-calculated after each operation.
  It is regularly synced to assure that calculations are correct.

Release 0.27.0
--------------

- Added volume size parameters configuration to instance creation process.
- Added management command for creating staff user with a password from cli.
- Increased timeouts for provisioning operations.

Release 0.26.0
--------------

- Extended NodeConductor admin with new models/fields.
- Increased timeouts for volume and snapshot operations.
- Refactored key usage on provisioning - never fail fully.
- Multiple bugfixes.

Release 0.25.0
--------------

- Fixed usage statistic calculation to use average instead of summing.
- Refactored backup to accept user input.
- Refactored backup to use OpenStack volumes instead of volume backups. Drastic increase in speed.

Release 0.24.0
--------------

- Introduce vm instance restart action.
