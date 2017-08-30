Attachments on Swift storage
=========================

This addon allows to store the attachments (documents and assets) on 
OpenStack Object Storage (Swift)

Configuration
-------------

Activate Swift storage:

* Create or set the system parameter with the key ``ir_attachment.location``
  and the value in the form ``swift``.

Configure accesses with environment variables:

* ``SWIFT_HOST``
* ``SWIFT_ACCOUNT``
* ``SWIFT_PASSWORD``
* ``SWIFT_WRITE_CONTAINER``

Read-only mode:

The continer name and the key are stored in the attachment. So if you change the
``SWIFT_WRITE_CONTAINER`` or the ``ir_attachment.location``, the existing attachments
will still be read on their former container. But as soon as they are written over
or new attachments are created, they will be created on the new container or on
the other location (db or filesystem). This is a convenient way to be able to
read the production attachments on a replication (since you have the
credentials) without any risk to alter the production data.

This addon must be added in the server wide addons with (``--load`` option):

``--load=web,web_kanban,attachment_swift``
