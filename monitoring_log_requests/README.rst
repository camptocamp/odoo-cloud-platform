.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License

Monitoring: Requests Logging
============================

This addon is used to output in the logs informations about the user's
requests.  Data such as *what* is the request, *who* requested it and *how
much* time did it took to complete could then be extracted from the logs and
loaded in an analysis tool such as ElasticSearch/Kibana.

Each log line is a JSON with the monitored fields, so it is easier to parse.

The logs are prefixed with ``monitoring.http.requests`` so be sure to enable
this path in the log handler::

    - LOG_HANDLER=":WARNING,monitoring.http.requests:INFO"
