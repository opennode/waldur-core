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
