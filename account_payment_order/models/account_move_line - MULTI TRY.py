# © 2014-2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# © 2014 Serv. Tecnol. Avanzados - Pedro M. Baeza
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree
from odoo import models, fields, api
from odoo.osv import orm


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    partner_bank_id = fields.Many2one(
        'res.partner.bank', string='Partner Bank Account',
        help='Bank account on which we should pay the supplier')
    bank_payment_line_id = fields.Many2one(
        'bank.payment.line', string='Bank Payment Line',
        readonly=True)
    payment_line_ids = fields.One2many(
        comodel_name='account.payment.line',
        inverse_name='move_line_id',
        string="Payment lines",
    )

    # INSERT Payment Move line Multi
        payment_order_ok = fields.Boolean(
        compute="_compute_payment_order_ok",
    )
    # we restore this field from <=v11 for now for preserving behavior
    # TODO: Check if we can remove it and base everything in something at
    # payment mode or company level
    reference_type = fields.Selection(
        selection=[
            ('none', 'Free Reference'),
            ('structured', 'Structured Reference'),
        ],
        string='Payment Reference',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        default='none',
    )

    # END INSERT Payment Move line Multi

    # INSERT Payment Move line Multi
        
    @api.depends('payment_mode_id', 'move_id', 'move_id.line_ids',
                 'move_id.line_ids.payment_mode_id')
    def _compute_payment_order_ok(self):
        for move_line in self:
            payment_mode = (
                move_line.move_id.line_ids.filtered(
                    lambda x: not x.reconciled
                ).mapped('payment_mode_id')[:1]
            )
            if not payment_mode:
                payment_mode = move_line.payment_mode_id
            move_line.payment_order_ok = payment_mode.payment_order_ok

    @api.model
    def line_get_convert(self, line, part):
        """Copy supplier bank account from move_line to account move line"""
        res = super(AccountMoveLine, self).line_get_convert(line, part)
        if line.get('user_type_id') == 'dest' and line.get('move_line_id'):
            move_line = self.browse(line['move_line_id'])
            if move_line.user_type_id in ('1', '2'):
                res['partner_bank_id'] = invoice.partner_bank_id.id or False
        return res

    @api.multi
    def _prepare_new_payment_order(self, payment_mode=None):
        self.ensure_one()
        if payment_mode is None:
            payment_mode = self.env['account.payment.mode']
        vals = {
            'payment_mode_id': payment_mode.id or self.payment_mode_id.id,
        }
        # other important fields are set by the inherit of create
        # in account_payment_order.py
        return vals

    @api.multi
    def create_account_payment_line(self):
        apoo = self.env['account.payment.order']
        result_payorder_ids = []
        action_payment_type = 'debit'
        for move_l in self:
            if move_l.reconciled != 'false':
                raise UserError(_(
                    "The move line %s is already reconciled") % move_l.ref)
            if move_l.blocked != 'false':
                raise UserError(_(
                    "The move line %s is blocked for payment") % move_l.ref)
            if not move_l.move_id:
                raise UserError(_(
                    "No Journal Entry on invoice %s") % inv.number)
            if move_l.amount_residual > 0:
                raise UserError(_(
                    "You can only select outgoing payments. %s has nos amount to pay.") % move_l.ref)
            applicable_lines = move_l.move_id.line_ids.filtered(
                lambda x: (
                    not x.reconciled and x.payment_mode_id.payment_order_ok and
                    x.account_id.internal_type in ('receivable', 'payable') and
                    not x.payment_line_ids
                )
            )
            if not applicable_lines:
                raise UserError(_(
                    'No Payment Line created for invoice %s because '
                    'it already exists or because this move line is '
                    'already paid.') % move_l.number)
            payment_modes = applicable_lines.mapped('payment_mode_id')
            if not payment_modes:
                raise UserError(_(
                    "No Payment Mode on Move Line %s") % move_l.ref)
            for payment_mode in payment_modes:
                payorder = apoo.search([
                    ('payment_mode_id', '=', payment_mode.id),
                    ('state', '=', 'draft')
                ], limit=1)
                new_payorder = False
                if not payorder:
                    payorder = apoo.create(move_l._prepare_new_payment_order(
                        payment_mode
                    ))
                    new_payorder = True
                result_payorder_ids.append(payorder.id)
                action_payment_type = payorder.payment_type
                count = 0
                for line in applicable_lines.filtered(
                    lambda x: x.payment_mode_id == payment_mode
                ):
                    line.create_payment_line_from_move_line(payorder)
                    count += 1
                if new_payorder:
                    move_l.message_post(body=_(
                        '%d payment lines added to the new draft payment '
                        'order %s which has been automatically created.')
                        % (count, payorder.name))
                else:
                    move_l.message_post(body=_(
                        '%d payment lines added to the existing draft '
                        'payment order %s.')
                        % (count, payorder.name))
        action = self.env['ir.actions.act_window'].for_xml_id(
            'account_payment_order',
            'account_payment_order_%s_action' % action_payment_type)
        if len(result_payorder_ids) == 1:
            action.update({
                'view_mode': 'form,tree,pivot,graph',
                'res_id': payorder.id,
                'views': False,
                })
        else:
            action.update({
                'view_mode': 'tree,form,pivot,graph',
                'domain': "[('id', 'in', %s)]" % result_payorder_ids,
                'views': False,
                })
        return action

    # FIN INSERT Payment Move line Multi    
    
    
    
    
    @api.multi
    def _prepare_payment_line_vals(self, payment_order):
        self.ensure_one()
        assert payment_order, 'Missing payment order'
        aplo = self.env['account.payment.line']
        # default values for communication_type and communication
        communication_type = 'normal'
        communication = self.move_id.ref or self.move_id.name
        # change these default values if move line is linked to an invoice
        if self.invoice_id:
            if self.invoice_id.reference_type != 'none':
                communication = self.invoice_id.reference
                ref2comm_type =\
                    aplo.invoice_reference_type2communication_type()
                communication_type =\
                    ref2comm_type[self.invoice_id.reference_type]
            else:
                if (
                        self.invoice_id.type in ('in_invoice', 'in_refund') and
                        self.invoice_id.reference):
                    communication = self.invoice_id.reference
                elif 'out' in self.invoice_id.type:
                    # Force to only put invoice number here
                    communication = self.invoice_id.number
        if self.currency_id:
            currency_id = self.currency_id.id
            amount_currency = self.amount_residual_currency
        else:
            currency_id = self.company_id.currency_id.id
            amount_currency = self.amount_residual
            # TODO : check that self.amount_residual_currency is 0
            # in this case
        if payment_order.payment_type == 'outbound':
            amount_currency *= -1
        partner_bank_id = False
        if not self.partner_bank_id:
            # Select partner bank account automatically if there is only one
            if len(self.partner_id.bank_ids) == 1:
                partner_bank_id = self.partner_id.bank_ids[0].id
        else:
            partner_bank_id = self.partner_bank_id.id
        vals = {
            'order_id': payment_order.id,
            'partner_bank_id': partner_bank_id,
            'partner_id': self.partner_id.id,
            'move_line_id': self.id,
            'communication': communication,
            'communication_type': communication_type,
            'currency_id': currency_id,
            'amount_currency': amount_currency,
            # date is set when the user confirms the payment order
            }
        return vals

    @api.multi
    def create_payment_line_from_move_line(self, payment_order):
        aplo = self.env['account.payment.line']
        for mline in self:
            aplo.create(mline._prepare_payment_line_vals(payment_order))
        return

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        # When the user looks for open payables or receivables, in the
        # context of payment orders, she should focus primarily on amount that
        # is due to be paid, and secondarily on the total amount. In this
        # method we are forcing to display both the amount due in company and
        # in the invoice currency.
        # We then hide the fields debit and credit, because they add no value.
        result = super(AccountMoveLine, self).fields_view_get(view_id,
                                                              view_type,
                                                              toolbar=toolbar,
                                                              submenu=submenu)

        doc = etree.XML(result['arch'])
        if view_type == 'tree' and self._module == 'account_payment_order':
            if not doc.xpath("//field[@name='balance']"):
                for placeholder in doc.xpath(
                        "//field[@name='amount_currency']"):
                    elem = etree.Element(
                        'field', {
                            'name': 'balance',
                            'readonly': 'True'
                        })
                    orm.setup_modifiers(elem)
                    placeholder.addprevious(elem)
            if not doc.xpath("//field[@name='amount_residual_currency']"):
                for placeholder in doc.xpath(
                        "//field[@name='amount_currency']"):
                    elem = etree.Element(
                        'field', {
                            'name': 'amount_residual_currency',
                            'readonly': 'True'
                        })
                    orm.setup_modifiers(elem)
                    placeholder.addnext(elem)
            if not doc.xpath("//field[@name='amount_residual']"):
                for placeholder in doc.xpath(
                        "//field[@name='amount_currency']"):
                    elem = etree.Element(
                        'field', {
                            'name': 'amount_residual',
                            'readonly': 'True'
                        })
                    orm.setup_modifiers(elem)
                    placeholder.addnext(elem)
            # Remove credit and debit data - which is irrelevant in this case
            for elem in doc.xpath("//field[@name='debit']"):
                doc.remove(elem)
            for elem in doc.xpath("//field[@name='credit']"):
                doc.remove(elem)
            result['arch'] = etree.tostring(doc)
        return result

        

