Cloud Platform
==============

Install addons required for the Camptocamp Cloud platform, and that are
common to all platform providers.

* Provide a quick install that we can call at the setup / migration
  of a database
* Check if the environment variables are configured correctly according
  to the instance's environment (prod, integration, test or dev) to prevent
  data corruption between the environments (such as the integration server
  writing on the production object storage).
