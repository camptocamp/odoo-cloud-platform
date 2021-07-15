Attachments on S3 storage
=========================

This addon allows to store the attachments (documents and assets) on S3 or any
other S3-compatible Object Storage.

Configuration
-------------

Activate S3 storage:

* Create or set the system parameter with the key ``ir_attachment.location``
  and the value in the form ``s3``.
* Configure accesses with the following environment variables:

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
     - If set, the bucket and all its objects will be copied when the database is
       duplicated. The paths in the database will be updated to use the copy.
     - True
   * - ``AWS_EMPTY_ON_DBDROP``
     - If set, all the objects in the bucket will be deleted when the database is
       dropped.
     - True

Read-only mode:

The bucket and the file key are stored in the attachment. So if you change the
``AWS_BUCKETNAME`` or the ``ir_attachment.location``, the existing attachments
will still be read on their former bucket. But as soon as they are written over
or new attachments are created, they will be created on the new bucket or on
the other location (db or filesystem). This is a convenient way to be able to
read the production attachments on a replication (since you have the
credentials) without any risk to alter the production data.

This addon must be added in the server wide addons with (``--load`` option):

``--load=web,attachment_s3``

The System Parameter ``ir_attachment.storage.force.database`` can be customized to
force storage of files in the database. See the documentation of the module
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

Use the `{db}` placeholder to handle multi-tenancy.

On instances that hold multiple databases, it's preferable to have one bucket per database.

To handle this, you can insert the `{db}` placeholder in your bucket name variable ``AWS_BUCKETNAME``.
It will be replaced by the database name.
This will give you a unique bucketname per database.

Limitations
-----------

* You need to call ``env['ir.attachment'].force_storage()`` after
  having changed the ``ir_attachment.location`` configuration in order to
  migrate the existing attachments to S3.

* If ``AWS_EMPTY_ON_DBDROP`` is set, the bucket is not deleted because Digital Ocean
  takes days to delete it and you get an error message when trying to recreate it:
  This bucket is temporarily reserved for administrative purposes.
