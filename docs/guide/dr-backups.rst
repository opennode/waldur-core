Disaster recovery backups (DR backup)
-------------------------------------

DR backups allow to store store instances backups outside of one 
OpenStack deployment and restore it on other deployment.


How it works
++++++++++++

On DR backup creation NodeConductor creates cinder backups for each volume of 
the instance, stores instance metadata and pull swift records of cinder backups.

On DR backup restoration NodeConductor creates cinder backups in new tenant, 
based on swift records. After this it creates new volumes and restores cinder 
backups on them. Finally NodeConductor creates new instance based on restored 
volumes and backup metadata.


API calls
+++++++++

To create new DR backup - issue POST request with instance, backup name and
description to **/api/openstack-dr-backups/** endpoint. DR backup has fields
"state" and "runtime_state" that indicate backup creation progress.

It is possible to update DR backup name and description with POST request
agains **/api/openstack-dr-backups/<uuid>/** endpoint.

To restore DR backup - issue POST request with DR backup, new tenant and new
instance flavor against **/api/openstack-dr-backup-restorations/** endpoint.
Make sure that flavor is big enough for instance. You can check DR backup
metadata to get stored instance minimum ram, cores and storage. After success 
restoration start endpoint will URL of instance that should be restored 
from DR backup, field "state" of this instance indicates restoration process 
progress.

To create schedule of DR backups - use same endpoint as for regular backups
(**/api/openstack-backup-schedules/**) and additionally pass parameter 
"backup type" as "DR".

For more detailed endpoints description - please check endpoints docs.