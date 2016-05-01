from __future__ import unicode_literals

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from nodeconductor.openstack import models, executors, handlers


class Command(BaseCommand):
    help_text = "Add default security groups with given names to all tenants to tenants."

    def add_arguments(self, parser):
        parser.add_argument('names', nargs='+', type=str)

    def handle(self, *args, **options):
        names = options['names']
        default_security_groups = getattr(settings, 'NODECONDUCTOR', {}).get('DEFAULT_SECURITY_GROUPS')
        security_groups = []
        for name in names:
            try:
                group = next(sg for sg in default_security_groups if sg['name'] == name)
            except StopIteration:
                raise CommandError('There is no default security group with name %s' % name)
            else:
                security_groups.append(group)

        for spl in models.OpenStackServiceProjectLink.objects.all():
            if not spl.tenant:
                continue
            for group in security_groups:
                if spl.security_groups.filter(name=group['name']).exists():
                    self.stdout.write('Tenant %s already have security group %s' % (spl.tenant, group['name']))
                    continue
                spl.security_groups.create(name=group['name'], description=group['description'])
                try:
                    db_security_group = handlers.create_security_group(spl, group)
                except handlers.SecurityGroupCreateException as e:
                    self.stdout.write(
                        'Failed to add security_group %s to tenant %s. Error: %s' % (group['name'], spl.teannt, e))
                else:
                    executors.SecurityGroupCreateExecutor.execute(db_security_group, async=False)
                    self.stdout.write(
                        'Security group %s has been successfully added to tenant %s' % (group['name'], spl.tenant))
