import logging
import warnings

import pyzabbix
import requests
from requests.exceptions import RequestException
from requests.packages.urllib3 import exceptions


logger = logging.getLogger(__name__)


class ZabbixClientError(Exception):
    pass


class QuietSession(requests.Session):
    """Session class that suppresses warning about unsafe TLS sessions and clogging the logs.
    Inspired by: https://github.com/kennethreitz/requests/issues/2214#issuecomment-110366218
    """
    def request(self, *args, **kwargs):
        if not kwargs.get('verify', self.verify):
            with warnings.catch_warnings():
                if hasattr(exceptions, 'InsecurePlatformWarning'):  # urllib3 1.10 and lower does not have this warning
                    warnings.simplefilter('ignore', exceptions.InsecurePlatformWarning)
                warnings.simplefilter('ignore', exceptions.InsecureRequestWarning)
                return super(QuietSession, self).request(*args, **kwargs)
        else:
            return super(QuietSession, self).request(*args, **kwargs)


class ZabbixClient(object):
    """ Provides low-level operations with zabbix """

    def __init__(self, server, username, password):
        self.api = self._get_api(server, username, password)

    def get_or_create_host(self, host_name, visible_name, group_id, template_ids, interface_parameters):
        """ Create zabbix host with given parameters.

        Return (<host>, <is_created>) tuple as result.
        """
        if not self.api.host.exists(host=host_name):
            templates = [{'templateid': template_id} for template_id in template_ids]
            host_parameters = {
                "host": host_name,
                "name": visible_name,
                "interfaces": [interface_parameters],
                "groups": [{"groupid": group_id}],
                "templates": templates,
            }
            try:
                host = self.api.host.create(host_parameters)
            except (pyzabbix.ZabbixAPIException, RequestException) as e:
                raise ZabbixClientError('Cannot create host with parameters: %s. Exception: %s' % (host_parameters, e))
            return host, True
        else:
            try:
                host = self.api.host.get(filter={'host': host_name})[0]
            except (pyzabbix.ZabbixAPIException, RequestException) as e:
                raise ZabbixClientError('Cannot create get host with name "%s". Exception: %s' % (host_name, e))
            return host, False

    def delete_host_if_exists(self, host_name):
        """ Delete zabbix host by name.

        Return True if host was deleted successfully, False if host with such name does not exist.
        """
        try:
            hostid = self.api.host.get(filter={'host': host_name})[0]['hostid']
            self.api.host.delete(hostid)
        except (pyzabbix.ZabbixAPIException, RequestException) as e:
            raise ZabbixClientError('Cannot create delete host with name "%s". Exception: %s' % (host_name, e))
        except IndexError:
            return False
        return True

    def _get_api(self, server, username, password):
        unsafe_session = QuietSession()
        unsafe_session.verify = False

        api = pyzabbix.ZabbixAPI(server=server, session=unsafe_session)
        api.login(username, password)
        return api
