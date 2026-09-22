Attachments on S3 storage
=========================

This addon stores attachments (documents and assets) on S3 or any
S3-compatible object storage.

It implements the hooks from ``base_attachment_object_storage``. It is not a
general AWS client.

Configuration
-------------

Activate S3 storage:

* Create or set the system parameter ``ir_attachment.location`` to ``s3``.
* Configure access with the following environment variables:

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Values
   * - ``AWS_HOST``
     - Endpoint.
     - Not required if using AWS (defaults to s3.amazonaws.com).
   * - ``AWS_REGION``
     - Region
     - Required if using AWS.
   * - ``AWS_ACCESS_KEY_ID``
     - Access Key ID
     -
   * - ``AWS_SECRET_ACCESS_KEY``
     - Secret Access Key
     -
   * - ``AWS_BUCKETNAME``
     - Name of the bucket (AWS) or space (Digital Ocean)
     - Optional {db} placeholder
   * - ``AWS_DUPLICATE``
     - If set, objects are copied when the database is duplicated.
       Paths in the new database are updated to the copy.
     - True
   * - ``AWS_EMPTY_ON_DBDROP``
     - If set, objects in the bucket are deleted when the database is
       dropped.
     - True

Installing the module while ``AWS_BUCKETNAME`` is set creates the bucket,
sets ``ir_attachment.location`` to ``s3``, and migrates existing files.

Read-only mode:

The bucket and the file key are stored in the attachment
(``s3://bucket/key``). If you change ``AWS_BUCKETNAME`` or
``ir_attachment.location``, existing attachments are still read from their
former bucket. New writes go to the new bucket or location. This lets a
replica read production attachments without altering production data.

This addon must be added in the server-wide addons (``--load``) so the
database manager hooks (drop / duplicate / restore) are registered::

  --load=web,attachment_s3,monitoring_status,session_redis

The system parameter ``ir_attachment.storage.force.database`` can be
customized to force storage of files in the database. See
``base_attachment_object_storage``.

Examples
--------

With AWS::

  AWS_REGION=us-east-1
  AWS_BUCKETNAME=mybucket-{db}
  AWS_ACCESS_KEY_ID=XXX
  AWS_SECRET_ACCESS_KEY=XXX

With Digital Ocean::

  AWS_HOST=nyc1.digitaloceanspaces.com
  AWS_BUCKETNAME=myspace-{db}
  AWS_ACCESS_KEY_ID=XXX
  AWS_SECRET_ACCESS_KEY=XXX

Multi-tenancy
-------------

Use the ``{db}`` placeholder to handle multi-tenancy.

On instances that hold multiple databases, prefer one bucket per database.
Insert ``{db}`` in ``AWS_BUCKETNAME``. It is replaced by the database name.

Limitations
-----------

* Call ``env['ir.attachment'].force_storage()`` after changing
  ``ir_attachment.location`` to migrate existing attachments to S3.

* If ``AWS_EMPTY_ON_DBDROP`` is set, the bucket is not deleted because some
  providers (Digital Ocean) reserve the name for days after deletion.
