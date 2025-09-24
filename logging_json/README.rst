JSON Logging
============

This addon allows to output the Odoo logs in JSON.

Configuration
-------------

The json logging is activated with the environment variable
``ODOO_LOGGING_JSON`` set to ``1``.

In order to have the logs from the start of the server, you should add
``logging_json`` in the ``--load`` flag or in the ``server_wide_modules``
option in the configuration file.

You can split the logs in stderr and stdout with the environment variable
``ODOO_LOGGING_JSON_STDERR`` set to ``1``. In this case, the logs with a level
of WARNING or above will be sent to stderr, the others to stdout.
