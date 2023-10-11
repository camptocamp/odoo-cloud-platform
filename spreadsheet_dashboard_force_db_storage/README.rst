======================================
Spreadsheet Dashboard Force DB storage
======================================

This module allows to force storage of spreadsheet dashboard data in the database
instead of any external storage that is configured.

When using `base_attachment_object_storage`, Odoo attachments' binaries data that
are stored on object storage use a storage key that is computed according to the
content of the binary data (ie checksum).
It works well as long as they are not meant to be modified, since it avoids duplication
of identical content on the object storage.
However, the spreadsheet dashboard records' binary data is meant to be modified and
the default worksheet data still has to be duplicated among the spreadsheet dashboard
records, to allow modification for each spreadsheet.
