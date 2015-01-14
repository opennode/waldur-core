CHANGELOG
=========

Coming in the next release
--------------------------

(Fixes/changes that are in develop branch.)

Release 0.27.0
--------------

- Added volume size parameters configuration to instance creation process.
- Added management command for creating staff user with a password from cli.
- Increased timeouts for provisioning operations.

Release 0.26.0
--------------

- Extended NodeConductor admin with new models/fields.
- Increase timeouts for volume and snapshot operations.
- Refactored key usage on provisioining - never fail fully.
- Multiple bugfixes.

Release 0.25.0
--------------

- Fixed usage statistic calculation to use average instead of summing.
- Refactored backup to accept user input.
- Refactored backup to use OpenStack volumes instead of volume backups. Drastic increase in speed.

Release 0.24.0
--------------

- Introduce vm instance restart action.
