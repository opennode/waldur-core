from nodeconductor.logging.loggers import EventLogger, event_logger

from . import models


class PriceEstimateEventLogger(EventLogger):
    price_estimate = models.PriceEstimate

    class Meta:
        event_types = ('price_estimate_limit_updated',)
        event_groups = {
            'price_estimates': event_types,
        }


event_logger.register('price_estimate', PriceEstimateEventLogger)
