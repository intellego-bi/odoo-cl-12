from odoo import api, fields, models
from odoo.tools.translate import _

class cenabast_operador_logistico(models.Model):
    _name = 'cenabast.operador_logistico'
    _description = 'Courier Partner'

    name = fields.Char(
        'Name', size=64, required=True)
    code = fields.Char(
        'Code', size=3, required=True)
    active = fields.Boolean(
        'Active', default=True)

    _sql_constraints = [('name', 'unique(name)', 'Name must be unique!'),
                        ('code', 'unique(code)', 'Code must be unique!')]


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

    def _get_default_pricelist_id(self):
        try:
            if saleordertype_id == '5':
                pricelist = self.env['product.pricelist'].search(
                [
                    ('name','=', 'Cenabast'),
                ])
                if pricelist:
                    return pricelist
            else:
                return self.env['product.pricelist']
        except:
            return self.env['product.pricelist']

    def _get_default_operador_logistico(self):
        try:
            return self.env.ref('l10n_cl_cenabast.ol_tnt')
        except:
            return self.env['cenabast.operador_logistico']
            
            
    saleordertype_id = fields.Many2one(
        'cenabast.saleordertype',
        string='Sale Order Type',
        default=lambda self: self._get_default_saleordertype()
    )

    cenabast_purchase_order = fields.Char(
        'External Purchase Order', size=10)
        
    cenabast_sales_order = fields.Char(
        'External Sales Order', size=10)

    cenabast_operador_logistico_id = fields.Many2one(
        'cenabast.operador_logistico',
        string='Courier Partner',
        default=lambda self: self._get_default_operador_logistico()
    )
        
        
        
    @api.onchange('saleordertype_id')
    def _onchange_saleordertype_id(self):
        if self.saleordertype_id:
            if self.saleordertype_id.id == 5:
                pricelist = self.env['product.pricelist'].search(
                [
                    ('name','=', 'Cenabast'),
                ])
                if pricelist:
                     self.pricelist_id = pricelist.id
                else:
                    self.pricelist_id = self.pricelist_id
            else:
                self.pricelist_id = self.pricelist_id





