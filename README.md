# Cloud Platform

Camptocamp odoo addons used on our Cloud Platform.

## Introduction

On the platform we want to achieve having:

* No data stored on the local filesystem so we can move an instance
  between hosts and even have several running front-ends
* Metrics read from the logs or sent to Prometheus to monitor the instances
* Logs sent to ElasticSearch-Kibana structured as JSON for better searching

For the storage, we store all the attachments on a object storage such as S3 or
a S3 compatible one, and we store the werkzeug sessions on Redis.

## Setup

### Python dependencies

Libraries that must be added in ``requirements.txt``:

```
boto==2.42.0
redis==2.10.5
python-json-logger==0.1.5
statsd==3.2.1
```

### Server Environment

The server environments in `server_environment_files` must be at least:

* `prod`
* `integration`
* `test`
* `dev`

The exact naming is important, because the `cloud_platform` addon rely on these keys to know and check the running environment.


### Attachments in the Object Storage

* prod: stored RW in the object storage
 * `AWS_HOST`: depends of the platform
 * `AWS_ACCESS_KEY_ID`: depends of the platform
 * `AWS_SECRET_ACCESS_KEY`: depends of the platform
 * `AWS_BUCKETNAME`: `<client>-odoo-prod`
* integration:
 * `AWS_HOST`: depends of the platform
 * `AWS_ACCESS_KEY_ID`: depends of the platform
 * `AWS_SECRET_ACCESS_KEY`: depends of the platform
 * `AWS_BUCKETNAME`: `<client>-odoo-integration`
* test: attachments are stored in database

Besides, the attachment location should be set to `s3` (but this is
automatically done by the `install` methods of the `cloud_platform` module.
 * `ir.config_parameter` `ir_attachment.location`: `s3`

### Sessions in Redis

* prod:
 * `ODOO_SESSION_REDIS`: 1
 * `ODOO_SESSION_REDIS_HOST`: depends of the platform
 * `ODOO_SESSION_REDIS_PASSWORD`: depends of the platform
 * `ODOO_SESSION_REDIS_PREFIX`: `<client>-odoo-prod`
* integration:
 * `ODOO_SESSION_REDIS`: 1
 * `ODOO_SESSION_REDIS_HOST`: depends of the platform
 * `ODOO_SESSION_REDIS_PASSWORD`: depends of the platform
 * `ODOO_SESSION_REDIS_PREFIX`: `<client>-odoo-integration`
* test:
 * `ODOO_SESSION_REDIS`: 1
 * `ODOO_SESSION_REDIS_HOST`: depends of the platform
 * `ODOO_SESSION_REDIS_PASSWORD`: depends of the platform
 * `ODOO_SESSION_REDIS_PREFIX`: `<client>-odoo-test`
 * `ODOO_SESSION_REDIS_EXPIRATION`: `86400` (1 day)

### JSON Logging

At least on production and integration, activate:
* `ODOO_LOGGING_JSON`: 1
* Add ``logging_json`` in the ``server_wide_modules`` option in the
  configuration file

### Metrics (Statsd/Prometheus for Grafana)

Should be active at least on the production server

* `ODOO_STATSD`: 1
* `STATSD_CUSTOMER`: `<client>`
* `STATSD_ENVIRONMENT`: set if you want to send metrics for a special
  environment which does not match with the `server_environment`
* `STATSD_HOST`: depends of the platform
* `STATSD_PORT`: depends of the platform

### Automatic Configuration

Calling `ctx.env['cloud.platform'].install_exoscale()` in an
`anthem` song will configure some parameters such as the
`ir_attachment.location` and migrate the existing attachments to the
object storage.


### Startup checks

At loading of the database, the addon will check if the environment variables
for Redis and the object storage are set as expected for the loaded
environment. It will refuse to start if anything is badly configured.

The checks can be bypassed with the environment variable
`ODOO_CLOUD_PLATFORM_UNSAFE` set to `1`.
