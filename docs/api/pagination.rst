Every NodeConductor REST request supports pagination. Links to the next, previous, first and last pages are included
in the Link header. *X-Result-Count* contains a count of all entries in the response set.

By default page size is set to 10. Page size can be modified by passing **?page_size=N** query parameter.

Example of the header output for user listing:

.. code-block:: http

    HTTP/1.0 200 OK
    Vary: Accept
    Content-Type: application/json
    Link:
     <http://example.com/api/users/?page=3>; rel="next",
     <http://example.com/api/users/?page=1>; rel="prev",
     <http://example.com/api/users/?page=6>; rel="last",
     <http://example.com/api/users/?page=1>; rel="first"
    X-Result-Count: 54
    Allow: GET, POST, HEAD, OPTIONS
