Billing integration
-------------------

NodeConductor can integrate with billing systems and expose typical features via REST API and admin interface.
At the moment, only KillBill_ is supported as a backend.

- pushing chargeback information from the services for invoice generation (based on resource and license consumption).
  Usages of resources is accounted on an hourly basis.
- getting invoice data from the backend (including generated PDFs).
- getting pricelists for products configured in the billing system. Monthly prices are assumed to be configured in KillBill.


.. _KillBill: https://killbill.io/

Configuration of integration with KillBill
++++++++++++++++++++++++++++++++++++++++++

Connecting NodeConductor with KillBill means defining KillBill API endpoint along with user credentials that have admin
access. API access for the NodeConductor service must be enabled in KillBill before connection can be established.

To setup a KillBill integration, add a billing block of configuration as shown in the example below.

.. code-block:: python

    # Example of settings for billing using WHMMCS API.
    NODECONDUCTOR['BILLING'] = {
        # billing driver
        'backend': 'nodeconductor.billing.backend.killbill.KillBillAPI',
        # url of billing API
        'api_url': 'http://killbill.example.com/1.0/kb/',
        # credentials
        'username': 'admin',
        'password': 'password',
        # tenant credentials
        'api_key': 'bob',
        'api_secret': 'lazar',
        # OpenStack service specific checks
        'openstack': {
            'invoice_meters': {
                # billing meter name: (resource name, pricelist name, unit)
                'cpu': ('CPU', 'cpu', 'hours'),
                'memory': ('Memory', 'ram_gb', 'GB/h'),
                'disk': ('Storage', 'storage_gb', 'GB/h'),
                'servers': ('Servers', 'server_num', ''),
                # license type: (display name, pricelist name, unit)
                'license_type': ('Sample license title', 'license_type', 'hours')
            }
        }
    }

Synchronisation with product prices of KillBill
+++++++++++++++++++++++++++++++++++++++++++++++

NodeConductor can populate its pricelist based on the configured products in KillBill.

The following conventions are in place:

- KillBill product names and descriptions are taken as pricelist item names in NodeConductor.
- KillBill monthly price is taken as an item price.

If you install from RPMs, the following monthly pricelist items will be synchronised:

- cpu
- ram_gb
- storage_gb
- server_num
- postgresql
- zimbra
- wordpress

Calculating a price for a IaaS template
+++++++++++++++++++++++++++++++++++++++

IaaS template monthly price should be calculated by the REST client as a sum of:

- flavor parameters multiplied by *cpu*, *ram_gb* and *storage_gb* pricelist items
- sum of template licenses types multiplied by the pricelist items names in lowercase (i.e. 'WordPress' license type
corresponds to 'wordpress' pricelist item).
