Base FileURL Field
==================

This module adds a new field type FileURL to Odoo.
FileURL is an extension of field type Binary, with the aim to store its
value on any kind of external storage.
It's been built with the focus on Amazon S3 but could be used with
other storage solution as long as it extends the functionality of
base_attachment_object_storage.

Usage
-----

FileURL fields is intended to store Binary data on an external storage
 with the possibility to be accessed outside of Odoo.

:param storage_location: Required external storage that must be
 activated on the system (cf base_attachment_storage)

:param storage_path: Path to be used as a prefix to the filename in the
 storage solution (must be used with filename)

:param filename: Field on the same model which stores the filename.
 Will be used to set fname on ir.attachment and, if storage_path is
 defined, will be passed to force the storage key.

Limitations / Issues
--------------------

* Filename must be stored in a separate field on the same model defining a FileURL field.
* While using storage_path and filename attributes, there's a risk existing storage object
  are overwritten if files with the same filename are added on different records.

Example
-------

cf `test_base_fileurl_field` module in https://github.com/camptocamp/odoo-cloud-platform
