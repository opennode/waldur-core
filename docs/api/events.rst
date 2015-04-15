Events list
-------------

To get a list of events, run GET against **/api/events/** as authenticated user. Note that a user can
only see events which is connected objects, that are visible for him.

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter. By default
events are sorted by @timestamp in descending order.

- ?o=\@timestamp
