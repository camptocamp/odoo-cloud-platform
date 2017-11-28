# Cloud Platform

Camptocamp odoo addons used on our Cloud Platform.

## Introduction

On the platform we want to achieve having:

* No data stored on the local filesystem so we can move an instance
  between hosts and even have several running front-ends
* Metrics read from the logs or sent to Prometheus to monitor the instances
* Logs sent to ElasticSearch-Kibana structured as JSON for better searching

For the storage, we store all the attachments on a object storage such as S3 or
 Swift, and we store the werkzeug sessions on Redis.

Two providers are available for the Cloud Platform, Exoscale based in
Switzerland and OVH in France.

The main difference between the two is the Object Store they use : 

* Exoscale uses S3
* OVH uses Swift

## Setup

### Python dependencies

Libraries that must be added in ``requirements.txt``:

```
redis==2.10.5
python-json-logger==0.1.5
statsd==3.2.1

# For S3 object storage (Exoscale, AWS)
boto==2.42.0

# For Swift object storage (OVH)
python-swiftclient==3.4.0
python-keystoneclient==3.13.0
```

### Odoo Startup

The `--load` option of Odoo must contains the following addons:

* `attachment_s3` or `attachment_swift` depending of the provider used.
* `session_redis`
* `logging_json`

Example:

`--load=web,attachment_s3,session_redis,logging_json`
`--load=web,attachment_swift,session_redis,logging_json`

### Server Environment

The server environments in `server_environment_files` must be at least:

* `prod`
* `integration`
* `test`
* `dev`

The exact naming is important, because the `cloud_platform` addon rely on these keys to know and check the running environment.


### Attachments in the Object Storage S3

* prod: stored RW in the object storage
 * `AWS_HOST`: depends of the platform
 * `AWS_REGION`: region's endpoint
 * `AWS_ACCESS_KEY_ID`: depends of the platform
 * `AWS_SECRET_ACCESS_KEY`: depends of the platform
 * `AWS_BUCKETNAME`: `<client>-odoo-prod`
* integration:
 * `AWS_ACCESS_KEY_ID`: depends of the platform
 * `AWS_SECRET_ACCESS_KEY`: depends of the platform
 * `AWS_BUCKETNAME`: `<client>-odoo-integration`
* test: attachments are stored in database

Besides, the attachment location should be set to `s3` (but this is
automatically done by the `install` methods of the `cloud_platform` module.
 * `ir.config_parameter` `ir_attachment.location`: `s3`


### Attachments in the Object Storage Swift

* prod: stored RW in the object storage
 * `SWIFT_AUTH_URL`: depends of the platform
 * `SWIFT_ACCOUNT`: depends of the platform
 * `SWIFT_PASSWORD`: depends of the platform
 * `SWIFT_WRITE_CONTAINER`: `<client>-odoo-prod`
* integration:
 * `SWIFT_AUTH_URL`: depends of the platform
 * `SWIFT_ACCOUNT`: depends of the platform
 * `SWIFT_PASSWORD`: depends of the platform
 * `SWIFT_WRITE_CONTAINER`: `<client>-odoo-integration`
* test: attachments are stored in database

Besides, the attachment location should be set to `swift` (but this is
automatically done by the `install` methods of the `cloud_platform` module.
 * `ir.config_parameter` `ir_attachment.location`: `swift`

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

An automatic configuration can be executed from an `anthem` song to configure
some parameters such as the `ir_attachment.location` and migrate the existing
attachments to the object storage.

It can be called like this: 
    `ctx.env['cloud.platform'].install(cloud_platform_kind)`
Replacing `cloud_platform_kind` with 'exoscale' or 'ovh'

Or using one of the direct shortcuts:

 * `ctx.env['cloud.platform'].install_exoscale()`
 * `ctx.env['cloud.platform'].install_ovh()`

### Startup checks

At loading of the database, the addon will check if the environment variables
for Redis and the object storage are set as expected for the loaded
environment. It will refuse to start if anything is badly configured.

The checks can be bypassed with the environment variable
`ODOO_CLOUD_PLATFORM_UNSAFE` set to `1`.
