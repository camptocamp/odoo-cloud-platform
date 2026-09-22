Base class for attachments on external object store
===================================================

This is a base addon that regroups common code used by addons targeting a
specific object store (S3, Azure, Swift).

It is not a complete storage backend. A companion module must implement
``_store_file_read``, ``_store_file_write``, ``_store_file_delete`` and
``_get_stores``.

Configuration
-------------

Object storage may be slow, and for this reason, we want to store
some files in the database whatever.

Small images (128, 256) are used in Odoo in list / kanban views. We
want them to be fast to read.
They are generally < 50KB (default configuration) so they don't take
that much space in database, but they'll be read much faster than from
the object storage.

The assets (application/javascript, text/css) are stored in database
as well whatever their size is:

* a database doesn't have thousands of them
* of course better for performance
* better portability of a database: when replicating a production
  instance for dev, the assets are included

This storage configuration can be modified in the system parameter
``ir_attachment.storage.force.database``, as a JSON value, for instance::

    {"image/": 51200, "application/javascript": 0, "text/css": 0}

Where the key is the beginning of the mimetype to configure and the
value is the limit in size below which attachments are kept in DB.
0 means no limit.

Default configuration means:

* images mimetypes (image/png, image/jpeg, ...) below 50KB are
  stored in database
* application/javascript are stored in database whatever their size
* text/css are stored in database whatever their size

Disable attachment storage I/O
------------------------------

Define an environment variable ``DISABLE_ATTACHMENT_STORAGE`` set to ``1``.
This will prevent any kind of exceptions and read/write on storage attachments.
