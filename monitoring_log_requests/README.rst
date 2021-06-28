.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License

Monitoring: Requests Logging
============================

This addon is used to output in the logs informations about the user's
requests.  Data such as *what* is the request, *who* requested it and *how
much* time did it took to complete.

The requests logging is activated with the environment variable `ODOO_REQUESTS_LOGGING` set to `1`.

Data output
###########

The data could then be extracted from the logs and
loaded in an analysis tool such as ElasticSearch/Kibana.

Each log line is a JSON with the monitored fields, so it is easier to parse.

The logs are prefixed with ``monitoring.http.requests`` so be sure to enable
this path in the log handler::

    - LOG_HANDLER=":WARNING,monitoring.http.requests:INFO"

It is also possible to send the data directly to an UDP listener without
outputting anything to the logs to avoid flooding on busy instances.
To do so, use the environment variable `ODOO_REQUESTS_LOGGING_UDP`
set to a value like `<address>:<port>` (`address` can be an IP or a domain).