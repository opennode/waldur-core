CHANGELOG
=========

Changelog has been moved to `http://docs.waldur.com/Changelog
<http://docs.waldur.com/Changelog>`_

Release NEXT
------------
- Raise an ElasticsearchClientError if ELASTICSEARCH configuration keys are missing or empty.
- Allow to filter user by civil number.
- Don't render superuser status. Drop unused viewsets.
- Add LDAP scheme to service settings backend_url validator.
- Add organization cost limit.

Release 0.135.0
---------------
- Introduce ram, vcpu, storage quotas to service project link.
- Drop SynchronizationStates, SynchronizationStateFilter, SynchronizableMixin.
- Add Default Price List Items action "Reinit configurations".

Release 0.134.0
---------------
- Drop django-permission.
- Restructure admin menu.

Release 0.133.0
---------------
- Remove inner HEAD requests from counter views.
- Update start time of virtual machine if runtime state changed.
- Drop VirtualMachineMixin.
- Allow to define user email on invitation accept.

Release 0.132.0
---------------
- Integrate JSONEditor widgets from django-jsoneditor for JSON fields in admin.
- Make shared field more visible on service settings creation form.
- Hide non-relevant fields for selected service on service settings creation form.
- Make ability for org owners to manage other org owners configurable.
- Allow to enable/disable backend fields and quotas editing on admin.

Release 0.131.0
---------------
- VirtualMachine user_data is no longer validated against safe yml format.
- Mark subresources as SPL children.

Release 0.130.0
---------------
- Enable i18n.
- Added "export_api_docs" management command for creating offline API Swagger descriptions.
- Bugfixes.

Release 0.129.0
---------------
- Reorganize admin dashboard. Add links to shared settings and resources.
- Introduce SubResources concept.
- Remove old style Resource.

Release 0.128.0
---------------
- Allow customer to limit project services by certificates.
- Add validation state and message to resources.
- Forbid resource creation is service project link is created from a service that does not satisfy project requirements.

Release 0.127.1
---------------
- Render token for the current user.

Release 0.127.0
---------------
- Disable service setting name update via service endpoint.

Release 0.126.2
---------------
- Fix settings fields values overlap issue on settings creation.

Release 0.126.1
---------------
- Validate role expiration time for permission granting user.
- Fix settings name update through service name update.

Release 0.126.0
---------------
- Migrate to Django 1.9
- Add minimum schedule value validator.
Now it is possible to set minimum time frame for resource schedule operations.
- Drop django-gm2m dependency.
- Replace django.conf.urls.patterns with list of urls.
- Allow to define geolocation for service settings.

Release 0.125.0
---------------
- Change external and internal ips to property. Force all models inherited from VirtualMachineMixin to define external
and internal ips properties.
- Remove name from service, service settings name is used instead.
- Introduce and connect certification model to service settings.

Release 0.124.0
---------------
- Logging cleanup.
- Limit admin session life time to 1h by default, made it configurable.
- Implemented penalized background task for reducing load from polling of services in down state.

Release 0.123.0
---------------
- Allow user to define his token lifetime.
- On update, instance is not returned in the old state anymore.
- Move throttling tasks from openstack plugin into structure.

Release 0.122.0
---------------
- Add field "domain" to service settings.

Release 0.121.1
---------------
- Make actions metadata renderer more generic so that it can be used for support offering.
- Allow to order customer and project users by concatenated name.
- Improve Swagger schema generator.

Release 0.121.0
---------------
- Display customer as "organization" in /admin.
- Allow user to grant new role and set expiration time simultaneously.

Release 0.120.0
---------------
- Allow user to be in any role simultaneously.
- Merge BaseResourceStateFilter with BaseResourceFilter and remove BaseResourceStateFilter.
- Fix permission deletion by making is_active field nullable.

Release 0.119.1
---------------
- Fix customer permission visibility issue.

Release 0.119.0
---------------
- Fix token authentication according to DRF 3.3.
- Replace IPAddressField serializer with DRF serializer.
- Add get_extra_kwargs method to AugmentedSerializerMixin.
- Migrate to DRF 3.5.3 and django_filter 0.15.3.
- Drop DjangoMappingFilterBackend and UUIDFilter.

Release 0.118.0
---------------
- Check if user has already accepted terms of service when he updates profile.

Release 0.117.0
---------------
- Show user description only to staff users.

Release 0.116.0
---------------
- Fix ProjectAdminForm.
- Drop UpdateOnlyStableMixin and UserContextMixin.
- Fix projects' get_users method.
- Add is_support field to User model.
- Add Support role to project and customer roles.
- Enable filtering user by customer and project UUID.

Release 0.115.0
---------------
- Add RuntimeStateValidator
- Fix access permissions.

Release 0.114.0
---------------
- Drop project groups.
- Implement permission mixin, project and customer permissions.
- Implement ability to set role deprecation time.
- Implement endpoint to get history of authorized personnel by period.

Release 0.113.1
---------------
- Fix ActionsMetadata.

Release 0.113.0
---------------
- Fix ActionsViewSet.
- Implement ResourceViewSet.

Release 0.112.1
---------------
- Implement ActionsViewSet and ActionsPermision.

Release 0.112.0
---------------
- Drop MySQL and SQLite3 database backend support.
- Remove SerializableAbstractMixin for serialization and reuse core.utils instead.

Release 0.111.0
---------------
- Added missing resource events.
- Fixed lookup and grouping of event groups.
- Allow staff to filter customer by user UUID.

Release 0.110.0
---------------
- Added agreement_date field to User model.
- Extended resources privileges for project managers.

Release 0.109.0
---------------
- Introduced user invitations.
- Add "registration_method" field to user model.

Release 0.108.3
---------------
- Introduce new abstract model Storage.

Release 0.108.2
---------------
- Fix filtering price estimate by customer UUID.
- Use separate queue for background tasks.
- Fix service settings sync task.
- Refactor PrivateCloudMixin -> PrivateCloud abstract model.
- Allow to use custom responses with @safe_operation decorator.

Release 0.108.1
---------------
- Don't use urllib3 1.18 because it's not compatible with old setuptools.

Release 0.108.0
---------------
- Introduction of usage-based price estimatation and billing.
- Prohibit editting of price estimates manually.
- Preserve consumption details of resources.
- Refactor price estimates calculation for link and unlink operations.
- Remove "resource provisioned" signal.
- Add admin action for recalculation of price estimates.
- Display resource consumption details in admin.
- Introduce base class for background tasks.

Release 0.107.1
---------------
- Bumped django-model-utils dependency version to 2.5.2.

Release 0.107.0
---------------
- Migrated to Django 1.8 UUIDField.

Release 0.106.0
---------------
- Validate UUID in filters.

Release 0.105.0
---------------
- Fix scoped service settings descendant resource unlinking.
- Enable HTTP client debugging.

Release 0.104.1
---------------
- Revert damage to /admin (upgrade strongly suggested).

Release 0.104.0
---------------
- Render actions metadata for new resources.
- Historical resource calculation is made optional.
- Fix Sentry integration.
- Implemented unlinking provider with all resources.
- Expose creation time of resources in /admin.
- Make service models quota-aware.
- Silence failed sync actions if resources was already erred.

Release 0.103.0
---------------
- Remove specific signals that handles user/ssh key management.
- Implement management command to cleanup invalid price estimates.
- Update metadata for price estimates of service, settings and project on scope deletion.
- Allow to update push hook token.
- Implement mixins to specify extra field metadata.

Release 0.102.5
---------------
- Removed incorrect wrapper.

Release 0.102.4
---------------
- Fix OpenStack client exception serialization in log_backend_action.

Release 0.102.3
---------------
- Rename PaidResource to PayableMixin. Track PriceEstimate for PayableMixin.
- Allow executing custom actions via templates after provision.

Release 0.102.2
---------------
- Cache resources and services tags.
- Allow to inject extra actions into model admin.

Release 0.102.1
---------------
- Introduce StructureLoggableMixin for filtering permitted object UUIDs.

Release 0.102.0
---------------
- Introduce VAT persistence and handling for customers.

Release 0.101.3
---------------
- Speedup services and resources load time.
- Provide view mixin for eager load.
- Add support for subscription to event groups.
- Fix service settings change view.
- Fix Travis build and documentation generation for plugin.

Release 0.101.2
---------------
- Fix documentation generation.

Release 0.101.1
---------------
- Bugfix.

Release 0.101.0
---------------
- Implement management command for cleaning up stale event types in hooks and system notifications.
- Rewrite hook summary view using SummaryQuerySet.
- Allow quotas to raise errors if their usage is over limit.
- Fix monitoring_items serializer.
- Verify VAT number using VIES checker and store it database.
- Fix filtering historic resources by customer.

Release 0.100.0
---------------
- Enable filtering shared service settings.
- Implement service-specific statistics endpoint.
- Rewrite service summary view using SummaryQueryset.
- Fix TLS support for Elasticsearch connections.

Release 0.99.1
--------------
- Bugfix.

Release 0.99.0
--------------
- Introduced ApplicationMixin for tracking Application resources.
- Bugfixes.

Release 0.98.0
--------------
- Expose groups for event types and alert types.
- Added group types for alerts and events.
- Cleaned up OpenStack dependencies from core.
- Bugfixes.

Release 0.97.0
--------------
- Added expiration time to authorization tokens.
- Fix filtering events by scope_type and time range.
- Implemented custom provider pricing configuration.
- Add filtering of resources by service counters by user visibility.
- Fixed push notifications through GCM.
- Bugfixes.

Release 0.96.0
--------------
- Preserve and restore tags for OpenStack backups.
- Support for provisioning of Zabbix-based monitoring-as-a-Service solutions.

Release 0.95.0
--------------
- Enhance collaborators permission logic.
- Implemented threshold-based alerts for price estimates and quotas.
- Prevent resource provisioning if total estimated cost of resource and project is over limit.

Release 0.94.0
--------------
- Extended events filter to support filtering by user and time frame.
- Enable filtering resource by category (vms, apps, private_clouds).
- Support permission, filters and metadata for OpenStack tenants.
- Added events hook to send them as push notification messages.
- Enable staff to define mandatory notifications.
- Emit resource state events for all resource models.
- Fix events filtering if resource URL is specified as scope.
- Fix ordering for /resources endpoint.
- Implement pull operation for OpenStack tenant.
- Provide filtering by required tags for resources and template groups endpoints.
- Created event type for project name update.
- Fix OpenStack license stats endpoint.
- Paginate results for customer users endpoint.
- Enable OpenStack tenant autocreation for service project links.
- Define default quotas for service project links.
- Add possibility to filter certain fields for projects/ and customers/ endpoints.

Release 0.93.0
--------------
- Added Resource import signal.
- Fixed quota update bug on cascade deletion.

Release 0.92.0
--------------
- Closed alerts are now cleaned up after a configured period (1 week by default).
- Moved documentation from RST files to docstrings.
- Added developer's section about API documentation.
- Bugfix: removed Django19 warnings.

Release 0.91.0
--------------
- Migrated to Django 1.8.
- Make quota usage readonly in /admin.
- Changed assing_floating_ip signature for OpenStack instances.
- Allow requesting specific REST fields to be rendered in a list.
- Added OpenStack Tenant resource and related operations.
- Documentation improvements.
- Removed state from the service project links.
- Bugfixes.

Release 0.90.0
--------------
- Introduced Executor layer for a single point of backend logic.
- Added migration script for moving iaas VMs to openstack module.
- Reworked price estimates to keep historical resource values and metadata.
- Exposed available resource actions through REST.
- Fixed quota duplication error.
- Dropped emitting of events about structure unit changes.
- Added tags filtering to resource views.
- Dropped Killbill dependency for OpenStack price estimates.
- Bugfixes.

Release 0.89.0
--------------
- Extracted Jira support app to plugin.
- Added synchronization during service settings recovery.
- Added admin command for shared service settings SPLs and services recreation.
- Added support for creating custom events by staff users.
- Implement generic quota aggregation.
- Add a management command for DRF API generation.
- Bugfixes.

Release 0.88.0
--------------
- Added additional quota types.
- Allow deletion of resources from ERRED state - for cleanup flows.

Release 0.87.0
--------------
- Added service setting quotas.
- Added new style aggregator quotas.
- Display connected projects and service of service settings.
- Bugfixes.

Release 0.86.0
--------------
- Extracted Oracle app to plugin.
- Moved SPLs and settings synchronization tasks to separate queue.
- Added documentation about the structure module.
- Refactored /admin for price estimates.
- Moved SPL synchronisation to a separate queue.
- Added quotas for service settings.
- Added CVS utils.
- NB! Fixed an issue with potential cleanup of floating IPs from all OpenStack tenants.
- Bugfixes.

Release 0.85.0
--------------
- Updated documentation for resource lifecycle events.
- Improved /admin interface, exposed installed plugins and versions.
- Made state rendering in /projects consistent.
- Fixed recovery command for service project links.
- Exposed subscription to Kill Bill and offline resources from admin page.
- Reimplemented resources summary view.
- Moved external_ips field to VirtualMachineMixin.
- Added model to resource viewset for permissions.
- Added ability to expose location with coordinates to VMs and resources.
- Added url field to /api/resources.
- Exposed OpenStack instance resize feature.
- Added a generic access_url field for Resource model.
- Added filter for default price list item in admin page.
- Refactored OpenStack Сelery tasks.
- Removed temporarily validation of TLS.
- Removed dev only app from test_settings.
- Extended DefaultPriceListItem with metadata.
- Fixed documentation typos.

Release 0.84.0
--------------
- Port OpenStack cost-tracking to using tags.
- Extract ldapsync application into a plugin.

Release 0.83.1
--------------
- Fix dependencies.

Release 0.83.0
--------------
- Added project filter to template groups.
- Added recovery transition from ERRED to SYNCING state for services.
- Cleanup dummy backends.
- Bugfixes.

Release 0.82.0
--------------
- Added ability to define service by settings and project on template provisioning.
- Tags were added to template groups.
- Exposed VM and non-VM counters in project REST view.
- Bugfixes.

Release 0.81.0
--------------
- Refactored template application adding capability to provision multiple resources in a row.

Release 0.80.0
--------------
- Exposed error_message field for each of the SynchronizableMixin-objects.
- Added role manipulation capability to /admin.
- Fixed filtering of the SLA view of IaaS resources.

Release 0.79.0
--------------
- Refactored cost tracking to make it pluggable.
- Refactor plugin system.
- Add events for failing and recovering Link and Service instances.
- Bugfixes.

Release 0.78.0
--------------
- Fix plugin support.
- Documentation updates.
- Bugfixes.

Release 0.77.0
--------------
- Refactor documentation to support plugins.
- Move OpenStack documentation to the plugins section.
- Add documentation section for SugarCRM plugin.
- Make services filtering by customer consistent.
- Fix OpenStack instance provisioning.
- Make admin page application names more user friendly.
- Bugfixes.

Release 0.76.0
--------------
- Bump supported versions of OpenStack libraries to Juno version.
- Implementation of lazy SPL creation for more efficient backend resource usage.
- Introduction of NEW and CREATION_SCHEDULED states for the SPLs.
- Added automatic OpenStack tenant deletion on OpenStack SPL removal.
- Fix maximum length for generated OpenStack and Zabbix names to fit into their model.
- Allow organisation claim to be modified by the claimer before it's confirmed.
- Bugfixes.

Release 0.75.0
--------------
- Multiple bugfixes.
- Added invoice generation.
- Add reporting of shared service consumption to KillBill.
- Enhanced cost esimation module.
- Dropped WHMCS billing, replaced with KillBill.io.
- New admin skin based on Fluent project.

Release 0.74.0
--------------
- Bugfixes.

Release 0.73.0
--------------
- Moved cost_tracking to IaaS.
- External net is now synced on CPM synchronization.
- Improved quotas timeline calculation.
- Improved price estimate computation.
- Improved WHMCS integration for instance lifecycle.
- Bugfixes.

Release 0.72.0
--------------
- Order tracking is now optional and configurable.
- Spaces are now allowed in price list item names.
- Improved Django admin list filtering.
- Dash and underscore are now allowed in a flavor name.
- Added a call to Zabbix registration on CPM sync.
- Added filters for OpenStack services and service-project links.
- Forced non-sudo mode on Travis.
- Changed filter names for the consistency.
- Added customer to filter fields list.
- Added filters for service and service-project link.
- Flavor name is now preserved on instance import.
- Added backup support for order tracking.
- Improved WHMCS integration.
- Improved documentation.

Release 0.71.0
--------------
- Moved to a container based Travis infrastructure.
- Replaced whistles.org with extranet.whistles.org in test data set.
- Max one license of specific type is now allowed.
- Removed IaaS template fees.
- Update versions of OpenStack libraries.
- Fixed Zabbix host and security groups creation on CPM creation.

Release 0.70.0
--------------
- UUID is now exposed for hooks.
- Non-staff user can now create new organizations.
- Fix project deletion.
- Implemented endpoint for price list items.
- Fixed stevedore dependency version.
- Improved price estimate API.
- Added ability to aggregate licenses by customer.
- Fix repository configuration step in install script.
- Added an option to list unmanaged resources.
- Zabbix hosts are now created for PaaS tenants.
- Added price list table endpoint.
- Price list creation and update are now done in one transaction.
- Added Azure service type.
- Instance security groups are now validated on instance provisioning.
- Added plugin settings configuration support.
- Logging improvements.
- Bugfixes.

Release 0.69.0
--------------
- Exact search is now used for username in permissions.
- Added AWS EC2 endpoint with support for import of a new resource.
- Connected services of a project are now exposed in REST API.
- Bugfixes.

Release 0.68.0
--------------
- Quotas are now changed before instance creation.
- Exposed date_joined attribute for user.

Release 0.67.0
--------------
- Enabled filtering service-project-link by project_uuid.
- Enabled filtering resources and backups by project_uuid.
- Added endpoints for price estimate calculation.

Release 0.66.0
--------------
- Proper error handling on SSH key removing.
- Implemented payments via Paypal.
- Fixed SupportedServices auto-discovery.
- Added resource quotas for projects and services.
- Improved resource filtering.
- Bugfixes.

Release 0.65.0
--------------
- Events are now routed from generation to notification according to subscription.
- Implemented historical data for event count.
- Update oslo.config dependency version.
- Implemented REST API for notifications subscription.
- Added external network creation task.
- Documentation improvements.

Release 0.64.0
--------------
- Alert statistics are moved to to alers app.
- Improve OpenStack router detection.
- Zero usage is now returned if usage is not available.
- Moved OpenStackSettings to ServiceSettings.
- Extended existing router detection.
- Remove deprecated OPENSTACK_CREDENTIALS settings.
- Documentation improvements.
- Bugfixes.

Release 0.63.0
--------------
- Added structure templates to mainfest.
- Fixed service settings editing in admin.
- Added merged resources view for all kinds of resources.
- Zabbix query optimizations.
- Added an option to provision JIRA projects.
- Added an option to manage GitLab groups/projects.
- Improved base service classes and add support of syncing users with backend.
- Bugfixes.
- Documentation improvements.

Release 0.62.0
--------------
- Implemented customer annual report generation.
- Added backup storage to invoice calculation.
- Added usage report generation in PDF.
- Implemented customer estimated price endpoint.
- Fix dummy client to work with CLI executions.
- Invoicing improvements.
- Bugfixes.

Release 0.61.0
--------------
- Improve performance of quotas timeline statistics API.
- Improved filters for alerts.
- Optimized query to Zabbix database for timeline stats.
- Fixed instance installation polling.
- Fixed OpenStack session initialization.
- Fixed documentation formatting.
- Fix tests for alerts.

Release 0.60.0
--------------
- Extended invoice generation with licensing data.
- Added ability to cancel alert acknowledgment.
- Added customers admin command for invoices creation.
- Added support for calculating monthly license usage.
- Documentation improvements.
- Test fixes.

Release 0.59.0
--------------
- Instance type is preserved on backup/restoration.
- Host IDs are now queried in Zabbix with a single call.
- UUID is now exposed at service projects list.

Release 0.58.0
--------------
- backup_source is now expoased in backup logging.
- Refactored price list synchronization with backend.
- Project admin and staff can now manage security groups and security group rules.
- Fix keystone session save and recover.
- Track keystone credentials instead of session itself.
- Implemented CPM security groups quotas.
- Logging improvements.
- Documentation improvements.

Release 0.57.0
--------------
- Issue status is now exposed over REST API.

Release 0.56.0
--------------
- Add endpoint for marking alerts as acknowledged.
- REST API for organization logo uploading.
- Added billing templates.
- Customer quotas are shown at customer endpoint.
- ProjectGroup viewset is now respecting user view permissions on project.
- Upgraded pysaml2 and djangosaml2 dependencies.
- Logging improvements.
- Bugfixes.

Release 0.55.1
--------------
- Added project_group field to project logging.

Release 0.55.0
--------------
- Bugfixes.
- Support billing data extraction from nova.

Release 0.54.0
--------------
- Alert API filtering extensions.
- Bugfixes of PaaS instance monitoring polling.

Release 0.53.0
--------------
- Extend alert filtering API.
- Bugfixes.

Release 0.52.0
--------------
- Alert filterting and statistics bugfixes.
- Support for application-specific Zabbix templates/checks.
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
- Bugfix: synchronize floating IP of OpenStack on membership synchronization.
- Exposure of several background tasks in admin.

Release 0.48.0
--------------
- Expose of requirements of mapped images in template list.
- UUID of objects is exposed in multiple endpoints.
- Bugfixes.

Release 0.47.0
--------------
- Added dummy JIRA client for faster development.
- Usability extensions of API: additional exposed fields and filterings.
- Support for user_data for OpenStack backend.
- Added dummy billing API.

Release 0.46.0
--------------
- Implemented foreground quotas for customers - support for limiting basic resources.
- Added dummy client for OpenStack backend. Allows to emulate actions of a backend for demo/development deployments.
- Added support for displaying, filtering and searching of events stored in Elasticsearch.
- Initial support of integration with JIRA for customer support.
  Bugfixes.

Release 0.45.0
--------------
- Migration to DRF 3.1 framework for REST, more consistent API.

Release 0.44.0
--------------
- Bugfixes.

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
- Support for setting CPU overcommit ratio for OpenStack versions prior to Kilo.
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
- UUIDs in emitted logs are not hyphenated.
- Bugfixes and documentation extensions.
- Default value for the maximal page_size was set to 200.

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
- Bugfixes.

Release 0.31.0
--------------
- Bugfixes.

Release 0.30.0
--------------
- Bugfixes.

Release 0.29.0
--------------
- Bugfixes.

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
- Introduce VM instance restart action.
