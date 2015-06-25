Billing integration
-------------------

NodeConductor can integrate with billing systems and expose typical features via REST API and admin interface.
At the moment, only WHMCS_ is supported as a backend.

- pushing chargeback information from the services for invoice generation
- getting invoice data from the backend (including generated PDFs)
- getting pricelists for products configured in the billing system.


.. _WHMCS: http://www.whmcs.com/

Configuration of integration
++++++++++++++++++++++++++++

Connecting NodeConductor with WHMCS means defining WHMCS API endpoint along with user credentials that have admin
access. API access for the NodeConductor service must be enabled in WHMCS before connection can be established.

To setup a WHMCS integration, add a billing block of configuration as shown in the example below.


.. code-block:: python

    # Example of settings for billing using WHMMCS API.
    NODECONDUCTOR['BILLING'] = {
        # billing driver
        'backend': 'nodeconductor.billing.backend.whmcs.WHMCSAPI',
        # url of billing API
        'api_url': 'http://demo.whmcs.com/includes/api.php',
        # credentials
        'username': 'Admin',
        'password': 'demo',
        # OpenStack service specific checks
        'openstack': {
            'invoice_meters': {
                # nova meter name: (resource name, pricelist name, unit converter, unit)
                'cpu': ('CPU', 'cpu_hours', 'hours'),
                'memory': ('Memory', 'ram_gb', 'GB/h'),
                'disk': ('Storage', 'storage_gb', 'GB/h'),
                'servers': ('Servers', 'server_num', ''),
            }
        }
    }
