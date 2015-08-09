from django.core.management.base import BaseCommand

from nodeconductor.iaas.models import Flavor, Instance


class Command(BaseCommand):

    def handle(self, *args, **options):
        for vm in Instance.objects.filter(billing_backend_id=''):
            if not vm.flavor_name:
                flavor = Flavor.objects.filter(cores=vm.cores, ram=vm.ram).first()
                if flavor:
                    vm.flavor_name = flavor.name
                    vm.save(update_fields=['flavor_name'])
                else:
                    self.stdout.write('! skip instance %s' % vm)
                    continue

            self.stdout.write('+ add order for instance %s' % vm)
            vm.order.add()

        self.stdout.write('... Done')
