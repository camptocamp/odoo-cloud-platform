Base class for attachments on external object store
===================================================

This is a base addon that regroups common code used by addons targeting specific object store.

When a module is installed or upgraded, this module moves any attachments to the configured object storage.
As there is no method to allow cleaning up the file system after a commit, the file are left in place.
Set the environment variable `ODOO_ADDON_BASE_ATTACHMENT_OBJECT_STORAGE_CLEAN_FILESYSTEM` to true to force
removing the copied file immediately.

