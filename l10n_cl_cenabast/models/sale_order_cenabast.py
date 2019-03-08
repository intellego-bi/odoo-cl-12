from odoo import api, fields, models
from odoo.tools.translate import _


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
#        default=lambda self: self._get_default_saleordertype()
    )

