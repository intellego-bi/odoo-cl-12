from odoo import api, fields, models
from odoo.tools.translate import _


class cenabast_saleordertype(models.Model):
    _name = 'cenabast.saleordertype'
    _description = 'Sale Order Type'

    name = fields.Char(
        'Name', size=64, required=True)
    code = fields.Char(
        'Code', size=3, required=True)
    active = fields.Boolean(
        'Active', default=True)

    _sql_constraints = [('name', 'unique(name)', 'Name must be unique!'),
                        ('code', 'unique(code)', 'Code must be unique!')]


class SaleOrderCenabast(models.Model):
    _inherit = 'sale.order'

    def _get_default_saleordertype(self):
        try:
            return self.env.ref('l10n_cl_cenabast.type_nacional')
        except:
            return self.env['cenabast.saleordertype']
    
    saleordertype_id = fields.Many2one(
        'cenabast.saleordertype',
        string='Sale Order Type',
        default=lambda self: self._get_default_saleordertype()
    )

