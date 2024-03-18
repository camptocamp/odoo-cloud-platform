# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{
    "name": "Attachments on S3 storage",
    "summary": "Store assets and attachments on a S3 compatible object storage",
    "version": "17.0.1.0.0",
    "author": "Camptocamp,Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "category": "Knowledge Management",
    "depends": ["base", "base_attachment_object_storage"],
    "external_dependencies": {
        "python": ["boto3"],
    },
    "website": "https://github.com/camptocamp/odoo-cloud-platform",
    "data": [],
    "installable": True,
}
