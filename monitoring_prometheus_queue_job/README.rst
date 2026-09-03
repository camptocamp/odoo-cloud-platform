.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License

=========================================
Monitoring: Prometheus metrics queue jobs
=========================================

Expose the number of queue jobs to Prometheus through the */metrics* endpoint
of ``monitoring_prometheus``.

The gauge ``odoo_queue_job_count`` is published with the labels *state* and
*channel*, for the states ``pending``, ``enqueued``, ``started``, ``failed``
and ``wait_dependencies``. The terminal states ``done`` and ``cancelled`` are
not reported.

Values are refreshed by the *Prometheus: gather metrics* scheduled action, so
they are a snapshot and not a real time count.

This module is automatically installed when both ``monitoring_prometheus`` and
``queue_job`` are installed.
