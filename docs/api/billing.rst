Price lookup
------------

To get a pricelist, run GET against **/api/billing/pricelist/** as an authenticated user.

Invoices
--------

To get a list of invoices, run GET against **/api/invoices/** as an authenticated user.

Filtering of invoices is supported through HTTP query parameters, the following fields are acceptable:

- ?customer=<customer uuid>
- ?month=<month>
- ?year=<year>

Invoice PDF
-----------

PDF version of invoice is available with GET against **/api/invoices/<invoice_uuid>/pdf/**.
In order to force browser to download and save PDF use **?download=1** parameter.


Invoice items
-------------

To get items of invoice run GET against **/api/invoices/<invoice_uuid>/items/**.


Invoices amount for customers
-----------------------------

PDF version of invoices sum for all customers is available against **/api/customers/annual_report/**.
To group invoices by month use **?group_by=month** parameter. Otherwise they will be grouped by customers.
In order to force browser to download and save PDF use **?download=1** parameter.


List payments
--------------------

To get a list of payments, run GET against **/api/payments/** as an authenticated user.
It contains the following fields:

- amount: specify total amount of money; the currency is specified in application's settings
- customer: URL of customer, because balance is related to particular customer

Example response:

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/payments/f85d62886e2d4947a9276d517f9516f3/",
            "uuid": "f85d62886e2d4947a9276d517f9516f3",
            "created": "2015-07-17T14:42:32.348Z",
            "modified": "2015-07-17T14:42:37.168Z",
            "state": "Created",
            "amount": "99.99",
            "customer": "http://example.com/api/customers/211ca3327de945899375749bd55dae4a/",
            "approval_url": "https://www.sandbox.paypal.com/cgi-bin/webscr?cmd=_express-checkout&token=EC-7YY98098HC144311S"
        }
    ]

Create new payment
-------------------------

In order to create new payment, run POST against **/api/payments/** as an authenticated user.
Request should contain the following fields: amount, customer. Example request:

.. code-block:: javascript

    {
        "amount": "99.99",
        "customer": "http://example.com/api/customers/211ca3327de945899375749bd55dae4a/"
    }

Response contains dictionary with single field named "approval_url". You should redirect to this URL in order to approve or cancel payment.
