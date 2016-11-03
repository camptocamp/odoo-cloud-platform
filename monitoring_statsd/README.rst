.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License

============================
Monitoring: Statsd metrics
============================

Send metrics to a Statsd (or Statsd compatible) server.

Currently, it sends:
 * time taken to process a click on a button
 * time taken to process a workflow signal
 * time taken by other requests

Configuration
=============

Activate with the environment variable:

* ``ODOO_STATSD=1``

Configure Statsd:

* ``STATSD_HOST=host``
* ``STATSD_PORT=port``

Configure differentiator:

* ``STATSD_CUSTOMER`` must contain the name of the client
* ``STATSD_ENVIRONMENT`` might contain the name of the environment, by
  default, it will use the ``server_environment``'s one
