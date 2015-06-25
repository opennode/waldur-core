from nodeconductor.logging.log import EventLogger, event_logger
from nodeconductor.billing import models


class InvoiceEventLogger(EventLogger):
    invoice = models.Invoice

    class Meta:
        event_types = ('invoice_deletion_succeeded',
                       'invoice_update_succeeded',
                       'invoice_creation_succeeded')


event_logger.register('invoice', InvoiceEventLogger)
