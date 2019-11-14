# -*- coding: utf-8 -*-
# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import _, api, fields, models
from datetime import datetime
from ..statsd_client import statsd, customer, environment
from ..sql_tracker import get_cursor_tracker


class IrCron(models.Model):
    _inherit = 'ir.cron'

    def _process_job(self, job_cr, job, cron_cr):
        name = u".".join([
            job['name'].replace('.', ' '),
            customer,
            environment,
            ])

        with statsd.pipeline() as pipe:
            pipe.gauge(u"cron_state.{}".format(name), 1)
            pipe.send()

            timer = pipe.timer(u"cron.{}".format(name)).start()
            res = super(IrCron, self)._process_job(job_cr, job, cron_cr)

            timer.stop()
            tracker = get_cursor_tracker()
            tracker.add_metric(pipe, u"cron_sql", name)
            pipe.gauge(u"cron_state.{}".format(name), 0)
        return res
