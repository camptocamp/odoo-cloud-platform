# Copyright 2017-2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{
    "name": "Cloud Platform Exoscale",
    "summary": "Addons required for the Camptocamp Cloud Platform on Exoscale",
    "version": "12.0.2.0.0",
    "author": "Camptocamp,Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "category": "Extra Tools",
    "depends": [
        "cloud_platform",
        "attachment_s3",
        "monitoring_statsd",
    ],
    "excludes": [
        "cloud_platform_ovh",
    ],
    "website": "https://github.com/camptocamp/odoo-cloud-platform",
    "data": [],
    "installable": True,
}
