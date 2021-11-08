# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{
    "name": "Cloud Platform Exoscale",
    "summary": "Addons required for the Camptocamp Cloud Platform on Exoscale",
    "version": "13.0.2.0.0",
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
        "cloud_platform_azure",
    ],
    "website": "https://www.camptocamp.com",
    "data": [],
    "installable": True,
}
