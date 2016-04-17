import calendar
from decimal import Decimal
import logging
import datetime

from celery import shared_task
from django.db import transaction, IntegrityError

from nodeconductor.iaas.models import Instance, InstanceSlaHistory
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError

logger = logging.getLogger(__name__)


def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month / 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return datetime.datetime.strptime('%s/%s/%s' % (day, month, year), '%d/%m/%Y')


@shared_task
def update_instance_sla(sla_type):
    if sla_type not in ('yearly', 'monthly'):
        logger.error('Requested unknown SLA type: %s' % sla_type)
        return

    dt = datetime.datetime.now()

    if sla_type == 'yearly':
        period = dt.year
        start_time = int(datetime.datetime.strptime('01/01/%s' % dt.year, '%d/%m/%Y').strftime("%s"))
    else:  # it's a monthly SLA update
        period = '%s-%s' % (dt.year, dt.month)
        month_start = datetime.datetime.strptime('01/%s/%s' % (dt.month, dt.year), '%d/%m/%Y')
        start_time = int(month_start.strftime("%s"))

    end_time = int(dt.strftime("%s"))

    instances = Instance.objects.exclude(
        state__in=[Instance.States.DELETING, Instance.States.PROVISIONING_SCHEDULED, Instance.States.PROVISIONING]
    ).exclude(backend_id='')
    zabbix_client = ZabbixApiClient()
    for instance in instances:
        try:
            logger.debug('Updating %s SLAs for instance %s. Period: %s, start_time: %s, end_time: %s' % (
                sla_type, instance, period, start_time, end_time
            ))
            current_sla, events = zabbix_client.get_current_service_sla(instance, start_time=start_time, end_time=end_time)

            with transaction.atomic():
                entry, _ = InstanceSlaHistory.objects.get_or_create(
                    instance=instance,
                    period=period
                )
                entry.value = Decimal(current_sla)
                entry.save()

                # update connected events
                for event in events:
                    event_state = 'U' if int(event['value']) == 0 else 'D'
                    entry.events.get_or_create(
                        timestamp=int(event['timestamp']),
                        state=event_state
                    )
        except ZabbixError as e:
            logger.warning('Zabbix error when updating current SLA values for %s. Reason: %s' % (instance, e))
        except IntegrityError as e:
            logger.warning('Could not update SLA values for %s due to concurrent update', instance)
        except Exception as e:
            logger.warning('Failed to update current SLA values for %s. Reason: %s' % (instance, e))
