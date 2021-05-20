# Copyright 2016-2019 Camptocamp SA
# Copyright 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
{
    "name": "Attachments on Azure storage",
    "summary": "Store assets and attachments on a Azure compatible object storage",
    "version": "14.0.1.0.0",
    "author": "Camptocamp, "
    "Open Source Integrators, "
    "Serpent Consulting Services, "
    "Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "category": "Knowledge Management",
    "depends": ["base_attachment_object_storage"],
    "external_dependencies": {
        "python": ["azure-storage-blob"],
    },
    "website": "https://github.com/camptocamp/odoo-cloud-platform",
    "installable": True,
    "development_status": "Beta",
    "maintainers": ["max3903"],
}
