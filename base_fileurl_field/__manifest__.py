# Copyright 2012-2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
{
    "name": "Base FileURL Field",
    "summary": "Implements of FileURL type fields",
    "category": "Technical Settings",
    "description": """
        This module adds a new field type FileURL to odoo.
        FileURL is an extension of field type Binary, with the aim to store its
         value on any kind external storage.
        It's been built with the focus on Amazon S3 but could be used with
         other storage solution as long as it extends the functionaly of
         base_attachment_object_storage.
    """,
    "version": "12.0.1.0.0",
    "depends": [
        "base_attachment_object_storage",
    ],
    "auto_install": False,
    "installable": True,
}
