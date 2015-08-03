from nodeconductor.cost_tracking.models import PriceKeysRegister, ServicePriceOptions, PriceListItem
from nodeconductor.oracle import models


class OracleServicePriceOptions(ServicePriceOptions):

    def get_service_class(self):
        return models.OracleService

    def get_service_keys_with_types(self):
        return (
            ('oracle-storage', PriceListItem.Types.STORAGE),
            ('oracle-license', PriceListItem.Types.LICENSE)
        )


def register():
    PriceKeysRegister.register(OracleServicePriceOptions())
