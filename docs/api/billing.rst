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


List PayPal payments
--------------------

To get a list of PayPal payments, run GET against **/api/payments/** as an authenticated user.
It contains the following fields:

- amount: specify total amount of money; the currency is specified in application's settings
- customer: URL of customer, because balance is related to particular customer
- success_url: after successfull approval of the payment user will be redirected to the specified URL
- error_url: if user has cancelled payment or error occurred during payment processing, he will be redirected to the specified URL

Example response:

.. code-block:: javascript

    [
        {
            "url": "http://www.example.com/api/payments/7d75f0ac023043e5822669af3e8b1931/",
            "uuid": "7d75f0ac023043e5822669af3e8b1931",
            "amount": "99.99",
            "created": "2015-07-16T09:05:27.113Z",
            "modified": "2015-07-16T09:10:51.463Z",
            "state": "Approved",
            "customer": "http://www.example.com/api/customers/211ca3327de945899375749bd55dae4a/",
            "success_url": "http://www.example.com/api/payments/success",
            "error_url": "http://www.example.com/api/payments/error"
        }
    ]

Create new PayPal payment
-------------------------

In order to create new PayPal payment, run POST against **/api/payments/** as an authenticated user.
Request should contain the following fields: amount, customer, success_url, error_url

Response contains dictionary with single field named "approval_url". You should redirect to this URL in order to approve or cancel payment.
