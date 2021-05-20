===========================================
Attachments on Microsoft Azure Blob Storage
===========================================

This addon allows to store the attachments (documents and assets) on `Microsoft Azure
Blob Storage <https://docs.microsoft.com/azure/storage/blobs/>`_.

Configuration
-------------

Activate Azure Blob storage:

* Create or set the system parameter with the key ``ir_attachment.location``
  and the value in the form ``azure``.

Configure accesses with environment variables:

* ``AZURE_STORAGE_CONNECTION_STRING`` or
* ``AZURE_STORAGE_ACCOUNT_NAME``
* ``AZURE_STORAGE_ACCOUNT_URL``
* ``AZURE_STORAGE_ACCOUNT_KEY``

One container will be created per database using the `RUNNING_ENV` environment variable
and the name of the database. By default, `RUNNING_ENV` is set to `dev`.

This addon must be added in the server wide addons with (``--load`` option):

``--load=web,attachment_azure``

The System Parameter ``ir_attachment.storage.force.database`` can be customized to
force storage of files in the database. See the documentation of the module
``base_attachment_object_storage``.

Limitations
-----------

* You need to call ``env['ir.attachment'].force_storage()`` after
  having changed the ``ir_attachment.location`` configuration in order to
  migrate the existing attachments to Azure Blob Storage.
