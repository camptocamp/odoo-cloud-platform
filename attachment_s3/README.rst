Attachments on S3 storage
=========================

This addon allows to store the attachments (documents and assets) on S3 or any
other S3-compatible Object Storage.

Configuration
-------------

Activate S3 storage:

* Create or set the system parameter with the key ``ir_attachment.location``
  and the value in the form ``s3``.

Configure accesses with environment variables:

* ``AWS_HOST`` (not required if using AWS services)
* ``AWS_REGION`` (required if using AWS services)
* ``AWS_ACCESS_KEY_ID``
* ``AWS_SECRET_ACCESS_KEY``
* ``AWS_BUCKETNAME``

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

Limitations
-----------

* You need to call ``env['ir.attachment'].force_storage()`` after
  having changed the ``ir_attachment.location`` configuration in order to
  migrate the existing attachments to S3.
