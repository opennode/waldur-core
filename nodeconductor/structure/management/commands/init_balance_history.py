from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from nodeconductor.structure.models import BalanceHistory
from nodeconductor.structure.models import Customer


class Command(BaseCommand):
    help = """ Initialize demo records of balance history """

    def handle(self, *args, **options):
        self.stdout.write('Creating demo records of balance history for all customers')
        for customer in Customer.objects.all():
            for i in range(10):
                BalanceHistory.objects.create(customer=customer,
                                              created=timezone.now() - timedelta(days=i),
                                              amount=100 + i * 10)

        self.stdout.write('... Done')
