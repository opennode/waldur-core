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

PDF version of invoice is available with GET against **/api/invoices/{uuid}/pdf/**
