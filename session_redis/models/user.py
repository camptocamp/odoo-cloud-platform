from openerp import models, tools


class User(models.Model):
    _inherit = 'res.users'

    @tools.ormcache('sid')
    def _compute_session_token(self, sid):
        """Make sure to return an unicode string.

        Odoo creates a session token using hexdigest Session which is str
        but with redis we set the token from a dictionary of values passing
        it in json format. When dumping values from json, we always get unicode
        thus both are incompatible.

        The shortest path is to fix the output of the computed session by Odoo.

        """
        return unicode(super(User, self)._compute_session_token(sid))
