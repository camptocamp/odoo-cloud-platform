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
scheduled action, which runs every 15 minutes and stores its result as
``prometheus.metric`` records (one per metric name/labels combination). The */metrics*
endpoint reads those records and publishes them as gauges. This indirection is required
because the cron and the HTTP workers run in separate processes and cannot share the
Prometheus registry.

By default, only users in the *Administration / Settings* group (``base.group_system``)
can read ``prometheus.metric`` records through the ORM/UI. The */metrics* endpoint
remains public and reads the records with ``sudo()`` so Prometheus can keep scraping it
without authentication.

To publish new metrics, extend ``_gather_metrics`` on the ``prometheus.gatherer``
abstract model and return the result of ``super()`` extended with your own entries::

    {
        "name": "odoo_some_metric",
        "documentation": "What this metric measures",
        "labels": {"label_name": "label_value"},
        "value": 42,
    }

