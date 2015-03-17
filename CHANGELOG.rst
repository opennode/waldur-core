CHANGELOG
=========

Coming in the next release
--------------------------

(Fixes/changes that are in develop branch.)

- Change OpenStack tenant name generation schema. Now it uses only project UUID, name is removed.


Release 0.40.0
--------------
- Enhanced support of instance import - added ability to set template.
- Fix sorting of instances by start_time.

Release 0.39.0
--------------
- Added instance import helper.
- Improved event logging.
- Bugfixes of quota checks.

Release 0.38.0
--------------

- Optimized resource usage monitoring. Use background tasks for collecting statistics.
- Bugfix of listing service events.

Release 0.37.0
--------------

- More information added to existing event logs.
- Improved performance of querying resource statistics.
- Bugfixes of the event logger and service list.

Release 0.36.0
--------------

- UUIDs in emitted logs are not hyphenated
- Bugfixes and documentation extensions
- Default value for the maximal page_size was set to 200

Release 0.35.0
--------------

- Added basic organization validation flow.
- Modified user filtering to take into account organization validation status.
- Bugfixes of the event logger.

Release 0.34.0
--------------

- Dropped backup quota. Rely on storage quota only.
- Added event logging for actions initiated by user or staff.

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
