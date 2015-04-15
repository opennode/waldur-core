Events list
-------------

To get a list of events, run GET against **/api/events/** as authenticated user. Note that a user can
only see events connected to objects she is allowed to see.

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter. By default
events are sorted by @timestamp in descending order.

- ?o=\@timestamp
