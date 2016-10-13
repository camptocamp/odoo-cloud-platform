Attachments on S3 storage
=========================

This addon allows to store the attachments (documents and assets) on S3 or any
other S3-compatible Object Storage.

Configuration
-------------

With system parameters:

* Create or set the system parameter with the key ``ir_attachment.location``
  and the value in the form ``s3://<access-key>:<secret-key>@<bucket-name>``
* If the host is not AWS services, you can set the key
  ``ir_attachment.s3.host`` to the hostname of the Object Storage
  service

With environment variables:

* Create or set the system parameter with the key ``ir_attachment.location``
  to ``s3://`` and configure the following environment variables:
  * ``AWS_HOST`` (not required if using AWS services)
  * ``AWS_ACCESS_KEY_ID``
  * ``AWS_SECRET_ACCESS_KEY``
  * ``AWS_BUCKETNAME``

Read-only mode:

You can configure the storage to be only for reads on the Object Storage.
This is convenient for replications/tests instances, that will be able to
access to the same content than the production database without any risk to
alter it. The files created or modified the read-only mode is active are
created in the database.

To activate the read-only mode, 2 possibilities:

* create the system parameter ``ir_attachment.s3.readonly`` and set a positive
  value (1, true)
* set the environment variable ``AWS_ATTACHMENT_READONLY`` to a positive
  value (1, true)

Limitations
-----------

When the addon is installed, files have already been created in the filesystem
or in the database. The addon won't automatically move them over the Object
storage. You can move them by calling the method ``force_storage`` on
``ir.attachment`` though (it might take time if you have many attachments).
