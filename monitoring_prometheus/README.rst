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
