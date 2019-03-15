# -*- coding: utf-8 -*-
# © 2016 Akretion (<https://www.akretion.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models, api


class AccountMoveLinePaymentLineMulti(models.TransientModel):
    _name = 'account.move.line.payment.line.multi'
    _description = 'Create payment lines from move line tree view'

    @api.multi
    def run(self):
        self.ensure_one()
        assert self._context['active_model'] == 'account.move.line',\
            'Active model should be account.move.line'
        move_lines = self.env['account.move.line'].browse(
            self._context['active_ids'])
        action = move_lines.create_account_payment_line()
        return action
