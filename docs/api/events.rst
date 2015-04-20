Events list
-------------

To get a list of events, run GET against **/api/events/** as authenticated user. Note that a user can
only see events connected to objects she is allowed to see.

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter. By default
events are sorted by @timestamp in descending order.

- ?o=\@timestamp

Filtering of customer list is supported through HTTP query parameters, the following fields are supported:

- ?event_type=<event_type> - type of filtered events. Can be list.
- ?search_text - text for FTS. FTS fields: 'message', 'customer_abbreviation', 'importance',
  'project_group_name', 'cloud_account_name', 'project_name'
