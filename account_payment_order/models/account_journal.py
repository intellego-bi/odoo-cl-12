# -*- coding: utf-8 -*-
# © 2019 Intellego-BI.com (https://www.intellego-bi.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _default_outbound_payment_methods(self):
        vals = super(AccountJournal, self)._default_outbound_payment_methods()
        return vals + self.env.ref('account_payment_order.cl_electronic')

        
    @api.model
    def _enable_electronic_outbound_on_bank_journals(self):
        """ Enables electronic credit transfer payment method on bank journals. Called upon module installation via data file.
        """
        cl_electronic = self.env.ref('account_payment_order.cl_electronic')
        clp = self.env.ref('base.CLP')
        if self.env.user.company_id.currency_id == clp:
            domain = ['&', ('type', '=', 'bank'), '|', ('currency_id', '=', clp.id), ('currency_id', '=', False)]
        else:
            domain = ['&', ('type', '=', 'bank'), ('currency_id', '=', clp.id)]
        for bank_journal in self.search(domain):
            bank_journal.write({'outbound_payment_method_ids': [(4, cl_electronic.id, None)]})

            
#    @api.model
#    def _create_batch_payment_outbound_sequence(self):
#        IrSequence = self.env['ir.sequence']
#        if IrSequence.search([('code', '=', 'account.outbound.batch.payment')]):
#            return
#        return IrSequence.sudo().create({
#            'name': _("Outbound Batch Payments Sequence"),
#            'padding': 4,
#            'code': 'account.outbound.batch.payment',
#            'number_next': 1,
#            'number_increment': 1,
#            'use_date_range': True,
#            'prefix': 'BATCH/OUT/%(year)s/',
#            #by default, share the sequence for all companies
#            'company_id': False,
#        })
 
#    @api.model
#    def _enable_electronic_outbound_on_bank_journals(self):
#        """ Enables electronic outbound payment method on bank journals. Called upon module installation via data file."""
#        cl_electronic = self.env.ref('account_payment_order.cl_electronic')
#        self.search([('type', '=', 'bank')]).write({
#                'outbound_payment_method_ids': [(4, cl_electronic.id, None)],
#        })

#    @api.multi
#    def open_action_batch_payment(self):
#        ctx = self._context.copy()
#        ctx.update({'journal_id': self.id, 'default_journal_id': self.id})
#        return {
#            'name': _('Create Batch Payment'),
#            'type': 'ir.actions.act_window',
#            'view_type': 'form',
#            'view_mode': 'form',
#            'res_model': 'account.batch.payment',
#            'context': ctx,
#        }
