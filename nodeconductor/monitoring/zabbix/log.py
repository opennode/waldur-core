from logging import Filter


class ZabbixLogsFilter(Filter):
    def filter(self, record):
        if record.getMessage().startswith('JSON-RPC Server Endpoint'):
            return False

        return super(ZabbixLogsFilter, self).filter(record)
