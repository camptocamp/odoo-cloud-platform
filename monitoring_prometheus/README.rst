.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License

==============================
Monitoring: Prometheus metrics
==============================

Add an endpoint */metrics* to allow a Prometheus server to fetch application metrics.
Current available metrics are:

* Request completion time with 3 differentiators:
  * Filestore
  * Assets
  * Everything else
* Longpolling request count

No additional configuration is needed, just ensure that the Prometheus server is allowed to communicate with Odoo

Gathering metrics from the database
-----------------------------------

Metrics that require a database query are collected by the *Prometheus: gather metrics*
scheduled action, which runs every 15 minutes and stores its result as JSON in the
``monitoring_prometheus.metrics`` system parameter. The */metrics* endpoint reads that
parameter and publishes the entries as gauges. This indirection is required because the
cron and the HTTP workers run in separate processes and cannot share the Prometheus
registry.

To publish new metrics, extend ``_gather_metrics`` on the ``prometheus.gatherer``
abstract model and return the result of ``super()`` extended with your own entries::

    {
        "name": "odoo_some_metric",
        "documentation": "What this metric measures",
        "labels": {"label_name": "label_value"},
        "value": 42,
    }

