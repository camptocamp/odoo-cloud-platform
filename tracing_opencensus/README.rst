Opencensus Tracing
==================

This addon allows to send tracing data to a Jaeger agent, using the opencensus library.

Configuration
-------------

The tracing is activated if the variable ``ODOO_OPENCENSUS_TRACING`` has the value ``1`` or ``true``.

Variables:

* ODOO_OPENCENSUS_TRACING: activate the tracing
* ODOO_OPENCENSUS_IGNORE_PATH: comma-separated list of URL paths to ignore in
  the tracing (by default: /longpolling)
* ODOO_OPENCENSUS_JAEGER_AGENT: host of the jaeger agent
* ODOO_OPENCENSUS_JAEGER_PORT: port of the jaeger agent


Limitations
-----------

While opencensus support several exporters and features, only a subset of them is supported:

* Only tracing is supported (no metrics, ...)
* Currently, the only exporter supported is the Jaeger exporter.

