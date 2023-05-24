# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models
from odoo.tools import config


class IrQweb(models.AbstractModel):

    _inherit = "ir.qweb"

    def _generate_asset_nodes_cache(
        self,
        bundle,
        css=True,
        js=True,
        debug=False,
        async_load=False,
        defer_load=False,
        lazy_load=False,
        media=None,
    ):
        context_for_printing = self.env.context.copy()
        if not config["test_enable"]:
            context_for_printing["commit_assetsbundle"] = True
        return super(
            IrQweb, self.with_context(**context_for_printing)
        )._generate_asset_nodes(
            bundle, css, js, debug, async_load, defer_load, lazy_load, media
        )
