CHANGELOG
=========

Coming in the next release
--------------------------

- <none yet>

Release 0.54.0
--------------
- Alert API filtering extensions.
- Bugfixes of PaaS instance monitoring polling.

Release 0.53.0
--------------
- Extend alert filtering API
- Bugfixes

Release 0.52.0
--------------
- Alert filterting and statistics bugfixes.
- Support for application-specific zabbix templates/checks.
- Alert endpoint for creating alerts with push.

Release 0.51.0
--------------
- Support for authentication token passing via query parameters.
- Alert API: historical and statistical.
- Support for historical quota usage/limit data via Zabbix backend.
- Filtering and minor API modifications across multiple endpoints.

Release 0.50.0
--------------
- New base structure for supporting of services.
- Support for NodeConductor extensions.
- Draft version of Oracle EM integration.
- Hook for invoice generation based on OpenStack Ceilometer data.
- Filtering and ordering API extensions.
- Draft of alerting API.

Release 0.49.1
--------------
- Bugfix of erred cloud recovery job.

Release 0.49.0
--------------
- Draft version of billing integration with WHMCS.
- Auto-recovery for CPMs if they pass health check.
- Demo API for the PaaS installation state monitoring.
- Bugfix: synchronise floating IP of OpenStack on membership synchronisation.
- Exposure of several background tasks in admin.

Release 0.48.0
--------------
- Expose of requirements of mapped images in template list.
- UUID of objects is exposed in multiple endpoints.
- Bugfixes

Release 0.47.0
--------------
- Added dummy Jira client for faster development.
- Usability extensions of API: additional exposed fields and filterings.
- Support for user_data for OpenStack backend.
- Added dummy billing API.

Release 0.46.0
--------------
- Implemented foreground quotas for customers - support for limiting basic resources.
- Added dummy client for OpenStack backend. Allows to emulate actions of a backend for demo/development deployments.
- Added support for displaying, filtering and searching of events stored in ElasticSearch.
- Initial support of integration with Jira for customer support.
  Bugfixes.

Release 0.45.0
--------------
- Migration to DRF 3.1 framework for REST, more consistent API.

Release 0.44.0
--------------
- Bugfixes

Release 0.43.0
--------------
- Extended IaaS template filtering.
- Extended IaaS template with os_type and icon_name fields.
- Renamed 'hostname' field to 'name' in Instance and Resources.

Release 0.42.0
--------------
- Refactored OpenStack backups to use snapshots instead of full volume backups.
- Moved OpenStack credentials to DB from configuration. Old credential format is still supported.
- Added support for TZ in backup schedule definition.
- Introduced throttling for background tasks.

Release 0.41.0
--------------
- Introducing new quotas module prototype. Support for backend and frontend quotas.
- Introducing new template module prototype. Support for multi-service templates.
- Support for default availability zone of OpenStack deployment in configuration.
- Support for setting cpu overcommit ratio for OpenStack versions prior to Kilo.
- Change OpenStack tenant name generation schema. Now it uses only project UUID, name is removed.
- More resilient start/stop operations for OpenStack.
- Extended event log information for instance creation.
- Bugfixes.

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
