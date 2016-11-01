# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import os


def migrate(cr, version):
    cr.execute("""
        SELECT value FROM ir_config_parameter
        WHERE key = 'ir_attachment.location'
    """)
    row = cr.fetchone()
    bucket = os.environ.get('AWS_BUCKETNAME')
    if row[0] == 's3' and bucket:
        cr.execute("""
            UPDATE ir_attachment
            SET store_fname = 's3://' || %s || '/' || store_fname
            WHERE store_fname IS NOT NULL AND store_fname NOT LIKE '%%/%%'
        """, (os.environ['AWS_BUCKETNAME'],))
