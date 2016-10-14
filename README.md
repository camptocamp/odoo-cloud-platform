# Cloud Platform

Camptocamp odoo addons used on our Cloud Platform.

## Introduction

On the platform we want to achieve having:

* no data stored on the local filesystem so we can move an instance
  between hosts and even have several running front-ends
* metrics read from the logs or sent to Prometheus to monitor the instances

For the storage, we store all the attachments on a object storage such as S3 or a S3 compatible one, and we store the werkzeug sessions on Redis.

For the metrics, we produce logs as json (TODO) that is sent
to ELK and send data to Prometheus/Grafana using statsd.

## Setup

### Python dependencies

Libraries that must be added in ``requirements.txt``:

```
boto==2.42.0
redis==2.10.5
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
* integration: stored RO in the production object storage, fallback
  on database for the writes
 * `AWS_HOST`: depends of the platform
 * `AWS_ACCESS_KEY_ID`: depends of the platform
 * `AWS_SECRET_ACCESS_KEY`: depends of the platform
 * `AWS_BUCKETNAME`: `<client>-odoo-prod` (this is normal, we read only the data)
 * `AWS_ATTACHMENT_READONLY`: `1`
* test: attachments are stored in database

Besides, the 
 * `ir.config_parameter` `ir_attachment.location`: `s3://` (

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
