# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
{
    "name": "Spreadsheet Dashboard Force DB Storage",
    "summary": "Force storage of attachments from spreadsheet dashboards in DB",
    "version": "16.0.1.0.0",
    "category": "Uncategorized",
    "website": "https://github.com/camptocamp/odoo-cloud-platform",
    "author": "Camptocamp",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "pre_init_hook": "pre_init_hook",
    "uninstall_hook": "uninstall_hook",
    "depends": [
        "spreadsheet_dashboard",
    ],
}
