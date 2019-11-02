# -*- coding: utf-8 -*-
# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from openerp.sql_db import Cursor
from openerp.http import request
import threading
from datetime import timedelta, datetime

threadLocal = threading.local()


class CursorTracker(object):

    def __init__(self):
        self.count = 0
        self.duration = timedelta(0)

    def add(self, duration):
        self.count += 1
        self.duration += duration


def get_cursor_tracker():
    current_local = request
    if not current_local:
        current_local = threadLocal
    if not hasattr(current_local, "_cursor_tracker"):
        setattr(current_local, "_cursor_tracker", CursorTracker())
    return current_local._cursor_tracker


ori_execute = Cursor.execute


def execute(self, query, params=None, log_exceptions=None):
    start = datetime.now()
    res = ori_execute(
        self, query, params=params, log_exceptions=log_exceptions)
    end = datetime.now()
    tracker = get_cursor_tracker()
    tracker.add(end-start)
    return res


Cursor.execute = execute
