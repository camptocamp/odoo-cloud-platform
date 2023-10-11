# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import SUPERUSER_ID, api


def pre_init_hook(cr):
    """Move binary data from storage to DB"""
    # Create DB column
    cr.execute("ALTER TABLE spreadsheet_dashboard ADD COLUMN data bytea NULL;")
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Read from storage
    records_data = env["spreadsheet.dashboard"].search_read(fields=["data"])
    # Write into DB
    for rec in records_data:
        cr.execute(
            "UPDATE spreadsheet_dashboard SET data = %s WHERE id = %s;",
            tuple([rec.get("data"), rec.get("id")]),
        )
    cr.execute("ALTER TABLE spreadsheet_dashboard ALTER COLUMN data SET NOT NULL;")
    # Delete attachments
    data_field = env["spreadsheet.dashboard"]._fields["data"]
    attachments = env["ir.attachment"].search(
        [
            ("name", "=", data_field.name),
            ("res_model", "=", data_field.model_name),
            ("res_field", "=", data_field.name),
            ("type", "=", "binary"),
            ("res_id", "in", [rec.get("id") for rec in records_data]),
        ]
    )
    attachments.unlink()


def uninstall_hook(cr, registry):
    """Move binary data from DB to storage"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Read from DB
    records_data = env["spreadsheet.dashboard"].search_read(fields=["data"])
    data_field = env["spreadsheet.dashboard"]._fields["data"]
    # Create attachments
    with env.norecompute():
        env["ir.attachment"].create(
            [
                {
                    "name": data_field.name,
                    "res_model": data_field.model_name,
                    "res_field": data_field.name,
                    "res_id": rec.get("id"),
                    "type": "binary",
                    "datas": rec.get("data"),
                }
                for rec in records_data
                if rec.get("data")
            ]
        )
    # Delete from DB
    cr.execute("ALTER TABLE spreadsheet_dashboard DROP COLUMN data;")
