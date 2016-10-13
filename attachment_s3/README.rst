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
  ``ir_attachment.location.s3host`` to the hostname of the Object Storage
  service

With environment variables:

* Create or set the system parameter with the key ``ir_attachment.location``
  to ``s3://`` and configure the following environment variables:
  * ``AWS_HOST`` (not required if using AWS services)
  * ``AWS_ACCESS_KEY_ID``
  * ``AWS_SECRET_ACCESS_KEY``
  * ``AWS_BUCKETNAME``

Limitations
-----------

When the addon is installed, files have already been created in the filesystem
or in the database. The addon won't automatically move them over the Object
storage. You can move them by calling the method ``force_storage`` on
``ir.attachment`` though (it might take time if you have many attachments).
