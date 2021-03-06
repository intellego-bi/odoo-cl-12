# © 2019 Intellego-BI.com (<http://www.intellego-BI.com>)
# © 2009 EduSense BV (<http://www.edusense.nl>)
# © 2011-2013 Therp BV (<https://therp.nl>)
# © 2016 Serv. Tecnol. Avanzados - Pedro M. Baeza
# © 2016 Akretion (Alexis de Lattre - alexis.delattre@akretion.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPaymentOrder(models.Model):
    _name = 'account.payment.order'
    _description = 'Payment Order'
    _inherit = ['mail.thread']
    _order = 'id desc'

    def domain_journal_id(self):
        if not self.payment_mode_id:
            return [('type','=','bank')]
        if self.payment_mode_id.bank_account_link == 'fixed':
            return [('id', '=', self.payment_mode_id.fixed_journal_id.id)]
        elif self.payment_mode_id.bank_account_link == 'variable':
            jrl_ids = self.payment_mode_id.variable_journal_ids.ids
            return [('id', 'in', jrl_ids)]

    def domain_payment_mode_id(self):
        for order in self:
            if order.payment_type == 'inbound':
                return [('payment_type','=','inbound')]
            elif order.payment_type == 'outbound':
                return [('payment_type','=','outbound')]
            else:
                return [('payment_type', '=', order.payment_type)]
            
    name = fields.Char(
        string='Number', readonly=True, copy=False)  # v8 field : name
    payment_type = fields.Selection([
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
        ], string='Payment Type', readonly=True, required=True)
    payment_mode_id = fields.Many2one(
        'account.payment.mode', 'Payment Mode', required=True,
        ondelete='restrict', track_visibility='onchange',
        domain=domain_payment_mode_id,
        readonly=True, states={'draft': [('readonly', False)]})
    payment_method_id = fields.Many2one(
        'account.payment.method', related='payment_mode_id.payment_method_id',
        readonly=True, store=True)
    company_id = fields.Many2one(
        related='payment_mode_id.company_id', store=True, readonly=True)
    company_currency_id = fields.Many2one(
        related='payment_mode_id.company_id.currency_id', store=True,
        readonly=True)
    bank_account_link = fields.Selection(
        related='payment_mode_id.bank_account_link', readonly=True)
    journal_id = fields.Many2one(
        'account.journal', string='Bank Journal', ondelete='restrict',
        readonly=True, states={'draft': [('readonly', False)]},
        domain=domain_journal_id,
        track_visibility='onchange')
    # The journal_id field is only required at confirm step, to
    # allow auto-creation of payment order from invoice
    company_partner_bank_id = fields.Many2one(
        related='journal_id.bank_account_id', string='Company Bank Account',
        readonly=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('open', 'Confirmed'),
            ('generated', 'File Generated'),
            ('uploaded', 'File Uploaded'),
            ('done', 'Done'),
            ('cancel', 'Cancel'),
        ], string='Status', readonly=True, copy=False, default='draft',
        track_visibility='onchange')
    date_prefered = fields.Selection([
        ('now', 'Immediately'),
        ('due', 'Due Date'),
        ('fixed', 'Fixed Date'),
        ], string='Payment Execution Date Type', required=True, default='due',
        track_visibility='onchange', readonly=True,
        states={'draft': [('readonly', False)]})
    date_scheduled = fields.Date(
        string='Payment Execution Date', readonly=True,
        states={'draft': [('readonly', False)]}, track_visibility='onchange',
        help="Select a requested date of execution if you selected 'Due Date' "
        "as the Payment Execution Date Type.")
    date_generated = fields.Date(string='File Generation Date', readonly=True)
    date_uploaded = fields.Date(string='File Upload Date', readonly=True)
    date_done = fields.Date(string='Done Date', readonly=True)
    generated_user_id = fields.Many2one(
        'res.users', string='Generated by', readonly=True, ondelete='restrict',
        copy=False)
    payment_line_ids = fields.One2many(
        'account.payment.line', 'order_id', string='Transaction Lines',
        readonly=True, states={'draft': [('readonly', False)]})
    # v8 field : line_ids
    bank_line_ids = fields.One2many(
        'bank.payment.line', 'order_id', string="Bank Payment Lines",
        readonly=True,
        help="The bank payment lines are used to generate the payment file. "
        "They are automatically created from transaction lines upon "
        "confirmation of the payment order: one bank payment line can "
        "group several transaction lines if the option "
        "'Group Transactions in Payment Orders' is active on the payment "
        "mode.")
    total_company_currency = fields.Monetary(
        compute='_compute_total', store=True, readonly=True,
        currency_field='company_currency_id')
    bank_line_count = fields.Integer(
        compute='_compute_bank_line_count', string='Number of Bank Lines',
        readonly=True)
    move_ids = fields.One2many(
        'account.move', 'payment_order_id', string='Journal Entries',
        readonly=True)
    description = fields.Char()

    @api.multi
    def unlink(self):
        for order in self:
            if order.state == 'uploaded':
                raise UserError(_(
                    "You cannot delete an uploaded payment order. You can "
                    "cancel it in order to do so."))
        return super(AccountPaymentOrder, self).unlink()

    @api.multi
    @api.constrains('payment_type', 'payment_mode_id')
    def payment_order_constraints(self):
        for order in self:
            if (
                    order.payment_mode_id.payment_type and
                    order.payment_mode_id.payment_type != order.payment_type):
                raise ValidationError(_(
                    "The payment type (%s) is not the same as the payment "
                    "type of the payment mode (%s)") % (
                        order.payment_type,
                        order.payment_mode_id.payment_type))

    @api.multi
    @api.constrains('date_scheduled')
    def check_date_scheduled(self):
        today = fields.Date.context_today(self)
        for order in self:
            if order.date_scheduled:
                if order.date_scheduled < today:
                    raise ValidationError(_(
                        "On payment order %s, the Payment Execution Date "
                        "is in the past (%s).")
                        % (order.name, order.date_scheduled))

    @api.multi
    @api.depends(
        'payment_line_ids', 'payment_line_ids.amount_company_currency')
    def _compute_total(self):
        for rec in self:
            rec.total_company_currency = sum(
                rec.mapped('payment_line_ids.amount_company_currency') or
                [0.0])

    @api.multi
    @api.depends('bank_line_ids')
    def _compute_bank_line_count(self):
        for order in self:
            order.bank_line_count = len(order.bank_line_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'account.payment.order') or 'New'
        if vals.get('payment_mode_id'):
            payment_mode = self.env['account.payment.mode'].browse(
                vals['payment_mode_id'])
            vals['payment_type'] = payment_mode.payment_type
            if payment_mode.bank_account_link == 'fixed':
                vals['journal_id'] = payment_mode.fixed_journal_id.id
            if (
                    not vals.get('date_prefered') and
                    payment_mode.default_date_prefered):
                vals['date_prefered'] = payment_mode.default_date_prefered
        return super(AccountPaymentOrder, self).create(vals)

    @api.onchange('payment_mode_id')
    def payment_mode_id_change(self):
        domain = self.domain_journal_id()
        res = {'domain': {
            'journal_id': domain
        }}
        journals = self.env['account.journal'].search(domain)
        if len(journals) == 1:
            self.journal_id = journals
        if self.payment_mode_id.default_date_prefered:
            self.date_prefered = self.payment_mode_id.default_date_prefered
        if self.payment_mode_id.payment_type:
            self.payment_type = self.payment_mode_id.payment_type
        return res

    @api.onchange('payment_type')
    def payment_type_change(self):
        domain = self.domain_payment_mode_id()
        res = {'domain': {
            'payment_mode_id': domain
        }}
        payment_modes = self.env['account.payment.mode'].search(domain)
        if len(payment_modes) == 1:
            self.payment_mode_id = payment_modes
        return res

        
        
    @api.multi
    def action_done(self):
        self.write({
            'date_done': fields.Date.context_today(self),
            'state': 'done',
            })
        return True

    @api.multi
    def action_done_cancel(self):
        for move in self.move_ids:
            move.button_cancel()
            for move_line in move.line_ids:
                move_line.remove_move_reconcile()
            move.unlink()
        self.action_cancel()
        return True

    @api.multi
    def cancel2draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def action_cancel(self):
        for order in self:
            order.write({'state': 'cancel'})
            order.bank_line_ids.unlink()
        return True

    @api.model
    def _prepare_bank_payment_line(self, paylines):
        return {
            'order_id': paylines[0].order_id.id,
            'payment_line_ids': [(6, 0, paylines.ids)],
            'communication': '-'.join(
                [line.communication for line in paylines]),
            }

    @api.multi
    def draft2open(self):
        """
        Called when you click on the 'Confirm' button
        Set the 'date' on payment line depending on the 'date_prefered'
        setting of the payment.order
        Re-generate the bank payment lines
        """
        bplo = self.env['bank.payment.line']
        today = fields.Date.context_today(self)
        for order in self:
            if not order.journal_id:
                raise UserError(_(
                    'Missing Bank Journal on payment order %s.') % order.name)
            if (
                    order.payment_method_id.bank_account_required and
                    not order.journal_id.bank_account_id):
                raise UserError(_(
                    "Missing bank account on bank journal '%s'.")
                    % order.journal_id.display_name)
            if not order.payment_line_ids:
                raise UserError(_(
                    'There are no transactions on payment order %s.')
                    % order.name)
            # Delete existing bank payment lines
            order.bank_line_ids.unlink()
            # Create the bank payment lines from the payment lines
            group_paylines = {}  # key = hashcode
            for payline in order.payment_line_ids:
                payline.draft2open_payment_line_check()
                # Compute requested payment date
                if order.date_prefered == 'due':
                    requested_date = payline.ml_maturity_date or today
                elif order.date_prefered == 'fixed':
                    requested_date = order.date_scheduled or today
                else:
                    requested_date = today
                # No payment date in the past
                if requested_date < today:
                    requested_date = today
                # inbound: check option no_debit_before_maturity
                if (
                        order.payment_type == 'inbound' and
                        order.payment_mode_id.no_debit_before_maturity and
                        payline.ml_maturity_date and
                        requested_date < payline.ml_maturity_date):
                    raise UserError(_(
                        "The payment mode '%s' has the option "
                        "'Disallow Debit Before Maturity Date'. The "
                        "payment line %s has a maturity date %s "
                        "which is after the computed payment date %s.") % (
                            order.payment_mode_id.name,
                            payline.name,
                            payline.ml_maturity_date,
                            requested_date))
                # Write requested_date on 'date' field of payment line
                payline.date = requested_date
                # Group options
                if order.payment_mode_id.group_lines:
                    hashcode = payline.payment_line_hashcode()
                else:
                    # Use line ID as hascode, which actually means no grouping
                    hashcode = payline.id
                if hashcode in group_paylines:
                    group_paylines[hashcode]['paylines'] += payline
                    group_paylines[hashcode]['total'] +=\
                        payline.amount_currency
                else:
                    group_paylines[hashcode] = {
                        'paylines': payline,
                        'total': payline.amount_currency,
                    }
            # Create bank payment lines
            for paydict in list(group_paylines.values()):
                # Block if a bank payment line is <= 0
                if paydict['total'] <= 0:
                    raise UserError(_(
                        "The amount for Partner '%s' is negative "
                        "or null (%.2f) !")
                        % (paydict['paylines'][0].partner_id.name,
                           paydict['total']))
                vals = self._prepare_bank_payment_line(paydict['paylines'])
                bplo.create(vals)
        self.write({'state': 'open'})
        return True

        
    @api.model
    def _truncate_str(self, texts, size=1, zerofill=1):
        c = 0
        f_string = ""
        text_str = str(texts)
        while c < size and c < len(text_str):
            f_string += text_str[c]
            c += 1
        f_string_out = f_string
        if zerofill == 0:
            f_string_out = f_string.zfill(size)
        return f_string_out        

    @api.model
    def _get_user_details(self, partner):
        """
        Get user details for Partner
        """
        first_name = ""
        last_name = ""
        mothers_name = ""
        if partner:
            ref_user_model = self.env['res.users']
            ref_user_recs = []
            user_recs = ref_user_model.search(['partner_id','=',partner])
            for users in user_recs:
                first_name = users.firstname
                last_name = users.last_name
                mothers_name = users.mothers_name
        #return (first_name, last_name, mothers_name)        
        return first_name        
        
        
    @api.multi
    def generate_payment_file(self):
        """Returns (payment file as string, filename)"""
        self.ensure_one()
        if self.payment_method_id.code == 'manual':
            return (False, False)
        else:
            date_today = fields.Date.context_today(self)

            if self.payment_mode_id.name == 'PRV - Transfer BCI':
                # Estructura de Archivo BANCO BCI - formato Texto
                # http://www.bci.cl/medios/2012/empresarios/capacitacion_pnol/archivos/estructura.pdf
                # http://www.bci.cl/medios/BCI2/pdf/Carga_Nomina.pdf

                f_file_name = str(self.name) + ' - ' + str(date_today) + ' - ' + str(self.payment_mode_id.name) + '.csv'

                payment_file_content = ""
                for payline in self.payment_line_ids:
                    f_rut = ""
                    f_rut_dv = ""
                    f_rut, f_rut_dv = payline.partner_id.document_number.split("-")
                    f_rut = f_rut.replace('.','')

                    # Inicio columnas archivo TXT
                    f_no_cta_cargo = self._truncate_str(self.company_partner_bank_id.acc_number, 12)
                    f_no_cta_destino = self._truncate_str(payline.partner_bank_id.acc_number, 18)
                    f_banco_destino = self._truncate_str(payline.partner_bank_id.bank_id.bic[-3:], 3)
                    f_rut_beneficiario = self._truncate_str(f_rut, 12)
                    f_digito_verif_beneficiario = self._truncate_str(f_rut_dv, 1)
                    f_nombre_beneficiario = self._truncate_str(payline.partner_id.name, 45)
                    f_monto_transferencia = self._truncate_str(payline.amount_company_currency, 16)
                    f_no_factura_boleta = self._truncate_str(payline.communication, 20)
                    f_no_orden_compra = self._truncate_str('', 20)
                    f_tipo_pago = 'PRV'
                    f_mensaje_destinatario = self._truncate_str('Pago Doc ' + str(payline.communication), 30)
                    if payline.partner_id.email:
                        f_email_destinatario = self._truncate_str(payline.partner_id.email, 45)
                    elif payline.partner_id.dte_email:
                        f_email_destinatario = self._truncate_str(payline.partner_id.dte_email, 45)
                    else:
                        f_email_destinatario = ""
                    f_cuenta_inscrita = self._truncate_str('R' + payline.partner_id.document_number.replace('.','') + ' C' + payline.partner_bank_id.acc_number, 25)
                    # Fin columnas archivo TXT

                    payment_file_content += f_no_cta_cargo + ';' + f_no_cta_destino + ';' + f_banco_destino + ';' + f_rut_beneficiario + ';' + f_digito_verif_beneficiario + ';' + f_nombre_beneficiario + ';' + f_monto_transferencia + ';' + f_no_factura_boleta + ';' + f_no_orden_compra + ';' + f_tipo_pago + ';' + f_mensaje_destinatario + ';' + f_email_destinatario + ';' + f_cuenta_inscrita + '\n'
                return (payment_file_content, f_file_name)
                
            elif self.payment_mode_id.name == 'REM - Transfer BCI':
                # Estructura de Archivo BANCO BCI - formato Texto
                # http://www.bci.cl/medios/2012/empresarios/capacitacion_pnol/archivos/estructura.pdf
                # http://www.bci.cl/medios/BCI2/pdf/Carga_Nomina.pdf

                f_file_name = str(self.name) + ' - ' + str(date_today) + ' - ' + str(self.payment_mode_id.name) + '.csv'

                payment_file_content = ""
                for payline in self.payment_line_ids:
                    f_rut = ""
                    f_rut_dv = ""
                    f_rut, f_rut_dv = payline.partner_id.document_number.split("-")
                    f_rut = f_rut.replace('.','')
                    # Inicio columnas archivo TXT
                    f_rut_beneficiario = self._truncate_str(f_rut, 8, 0)
                    f_digito_verif_beneficiario = self._truncate_str(f_rut_dv, 1)
                    f_no_cta_cargo = self._truncate_str(self.company_partner_bank_id.acc_number, 12)
                    f_no_cta_destino = self._truncate_str(payline.partner_bank_id.acc_number, 18)
                    f_banco_destino = self._truncate_str(payline.partner_bank_id.bank_id.bic[-3:], 3)
                    #t_first_name = self._get_user_details(payline.partner_id)
                    #f_nombre_beneficiario = self._truncate_str(t_first_name, 45)
                    f_nombre_beneficiario = self._truncate_str(payline.partner_id.name, 45)
                    f_monto_transferencia = self._truncate_str(payline.amount_company_currency , 16)
                    f_no_factura_boleta = self._truncate_str(payline.communication, 20)
                    f_no_orden_compra = self._truncate_str('', 20)
                    f_tipo_pago = 'REM'
                    f_mensaje_destinatario = self._truncate_str('Pago Remuneraciones ' + str(payline.date), 30)
                    if payline.partner_id.email:
                        f_email_destinatario = self._truncate_str(payline.partner_id.email, 45)
                    else:
                        f_email_destinatario = ""
                    f_cuenta_inscrita = self._truncate_str('R' + payline.partner_id.document_number.replace('.','') + ' C' + payline.partner_bank_id.acc_number, 25)
                    # Fin columnas archivo TXT

                    payment_file_content += f_rut_beneficiario + ';' + f_digito_verif_beneficiario + ';' + f_no_cta_cargo + ';' + f_no_cta_destino + ';' + f_banco_destino + ';' +  f_nombre_beneficiario + ';' + f_monto_transferencia + ';' + f_no_factura_boleta + ';' + f_no_orden_compra + ';' + f_tipo_pago + ';' + f_mensaje_destinatario + ';' + f_email_destinatario + ';' + f_cuenta_inscrita + '\n'

                    return (payment_file_content, f_file_name)

            elif self.payment_mode_id.name == 'PRV - Transfer Banco de Chile':
                # Estructura de Archivo BANCO CHILE - formato Texto
                # 
                # 
                count_payline = 0
                for cpayline in self.payment_line_ids:
                    count_payline += 1
                count_bankline = 0
                for cpayline in self.bank_line_ids:
                    count_bankline += 1
                t_filler = ""
                f_paga_rut = ""
                f_paga_rut_dv = ""
                f_paga_rut, f_paga_rut_dv = self.env.user.company_id.document_number.split("-")
                f_paga_rut = f_paga_rut.replace('.','')
                t_monto_nom, t_decn = str(self.total_company_currency).split(".")
                f_monto_nomina = str(t_monto_nom) + '00'

                f_file_name = str(self.name) + ' - ' + str(date_today) + ' - ' + str(self.payment_mode_id.name) + '.txt'

                payment_file_content = ""

                # Tipo Fila 01
                f_filler_01 = t_filler.ljust(564)

                payment_file_content = '01' + self._truncate_str(f_paga_rut, 10, 0) + str(f_paga_rut_dv) + self._truncate_str(f_monto_nomina, 13, 0) + self._truncate_str(count_bankline, 10, 0) + self._truncate_str(count_payline, 10, 0) + f_filler_01 + '\n'

                for bankline in self.bank_line_ids:
                    f_rut = ""
                    f_rut_dv = ""
                    f_rut, f_rut_dv = bankline.partner_id.document_number.split("-")
                    f_rut = f_rut.replace('.','')
                    t_monto, t_dec = str(bankline.amount_currency).split(".")
                    t_streets = str(bankline.partner_id.street) + ' ' + str(bankline.partner_id.street2)

                    # Tipo Fila 02
                    f_rut = self._truncate_str(f_rut, 10, 0)
                    f_nombre = self._truncate_str(bankline.partner_id.name.upper(), 60).ljust(60)
                    f_direccion = self._truncate_str(t_streets.upper(), 35).ljust(35)
                    f_comuna = self._truncate_str(bankline.partner_id.city.upper(), 15).ljust(15)
                    f_ciudad = self._truncate_str(bankline.partner_id.state_id.name.upper(), 15).ljust(15)
                    if bankline.partner_id.is_company:
                        f_act_eco = 'B1'   # Persona Jurídica
                    else:
                        f_act_eco = 'BC'   # Persona Natural                                     
                    f_monto_total = self._truncate_str(t_monto, 11, 0) + '00'
                    #f_date = self._truncate_str(self.date_generated.day, 2, 0) + self._truncate_str(self.date_generated.month, 2, 0) + str(self.date_generated.year)
                    f_date = self._truncate_str(date_today.day, 2, 0) + self._truncate_str(date_today.month, 2, 0) + str(date_today.year)
                    d_bancos = ['001','029','033']
                    if str(bankline.partner_bank_id.bank_id.bic[-3:]) in d_bancos:  
                        f_medio_pago = '01'  # Banco de Chile
                    else:
                        f_medio_pago = '07'  # Otros Bancos
                    f_banco_destino = self._truncate_str(bankline.partner_bank_id.bank_id.bic[-3:], 3)
                    f_oficina_destino = t_filler.ljust(3)
                    f_no_cta_destino = self._truncate_str(bankline.partner_bank_id.acc_number, 22).ljust(22)
                    f_descripcion_pago = self._truncate_str("PAGO DE " + str(self.env.user.company_id.name).upper(), 120).ljust(120)
                    f_ind_vva = " "
                    f_campos_libres_123 = t_filler.ljust(70)
                    f_contactos = t_filler.ljust(71)
                    f_fono_fax = t_filler.ljust(14)
                    if bankline.partner_id.email:
                        f_email_a = self._truncate_str(bankline.partner_id.email.upper(), 60).ljust(60)
                        f_canal_aviso = "1" 
                        f_num_aviso = self._truncate_str(bankline.name[-4:], 4)
                    else:
                        f_email_a = t_filler.ljust(60)
                        f_canal_aviso = " "
                        f_num_aviso = t_filler.ljust(4)
                    f_email_b = t_filler.ljust(60)
                    f_filler_02 = t_filler.ljust(18)                   

                    payment_file_content += '02' + f_rut + f_rut_dv +  f_nombre + f_direccion + f_comuna + f_ciudad + f_act_eco + f_monto_total + f_date + f_medio_pago + f_banco_destino + f_oficina_destino + f_no_cta_destino + f_descripcion_pago + f_ind_vva + f_campos_libres_123 + f_contactos + f_canal_aviso + f_fono_fax + f_email_a + f_email_b + f_num_aviso + f_filler_02 + '\n'

                    # Tipo Fila 03
                    for payline in self.payment_line_ids: 
                        if payline.partner_id == bankline.partner_id:
                            if payline.move_line_id.document_class_id:
                                f_tipo_doc = self._truncate_str(payline.move_line_id.document_class_id.sii_code, 3, 0)
                                f_doc = 'PAGO DE ' + payline.move_line_id.document_class_id.doc_code_prefix + ': '
                            else:
                                f_tipo_doc = self._truncate_str(payline.move_line_id.move_id.name, 3)
                                f_doc = 'PAGO DE DOC: '
                            f_num_factura_boleta = self._truncate_str(payline.communication, 10, 0).ljust(10)
                            f_num_cuota = '001'
                            f_monto_doc = self._truncate_str(payline.amount_company_currency, 11, 0) + '00'
                            #f_due_date = self._truncate_str(payline.ml_maturity_date.day, 2, 0) + self._truncate_str(payline.ml_maturity_date.month, 2, 0) + str(payline.ml_maturity_date.year)
                            f_doc_date = self._truncate_str(payline.move_line_id.move_id.date.day, 2, 0) + self._truncate_str(payline.move_line_id.move_id.date.month, 2, 0) + str(payline.move_line_id.move_id.date.year)
                            f_doc_descrip = self._truncate_str(f_doc + payline.communication + ' DE FECHA DOC = ' + str(payline.move_line_id.move_id.date) + ' Y VENCIM. = ' + str(payline.ml_maturity_date), 120).ljust(120)
                            f_campos_libres_123 = t_filler.ljust(70)
                            f_filler_03 = t_filler.ljust(368)   

                            payment_file_content += '03' + f_tipo_doc + f_num_factura_boleta + f_num_cuota + f_monto_doc + f_monto_doc + f_doc_date + f_doc_descrip + f_campos_libres_123 + f_filler_03 + '\n'

                    # Tipo Fila 04
                    l_num_aviso = 0
                    for apayline in self.payment_line_ids:       
                        if apayline.partner_id == bankline.partner_id and bankline.partner_id.email:
                            l_num_aviso += 1
                            for abankline in self.bank_line_ids: 
                                if abankline.order_id == apayline.order_id:
                                    f_num_aviso = self._truncate_str(abankline.name[-4:], 4)
                            if apayline.move_line_id.document_class_id:
                                f_tipo_doc = self._truncate_str(apayline.move_line_id.document_class_id.sii_code, 3, 0)
                                f_doc = apayline.move_line_id.document_class_id.doc_code_prefix + ': '
                            else:
                                f_tipo_doc = self._truncate_str(apayline.move_line_id.move_id.name, 3)
                                f_doc = 'DOC: '
                            f_monto_aviso = self._truncate_str(apayline.amount_company_currency, 11).ljust(11)
                            f_glosa_aviso = self._truncate_str("AVISO PAGO DE " + str(self.env.user.company_id.name).upper() + ' PARA ' + apayline.partner_id.name.upper() + ' DE SU ' + f_doc + apayline.communication + ' POR VALOR DE ' + f_monto_aviso, 320).ljust(320)
                            f_corr_aviso = self._truncate_str(str(l_num_aviso), 5, 0)
                            #f_due_date = self._truncate_str(payline.ml_maturity_date.day, 2, 0) + self._truncate_str(payline.ml_maturity_date.month, 2, 0) + str(payline.ml_maturity_date.year)
                            #f_doc_date = self._truncate_str(apayline.move_line_id.move_id.date.day, 2, 0) + self._truncate_str(apayline.move_line_id.move_id.date.month, 2, 0) + str(apayline.move_line_id.move_id.date.year)
                            f_filler_04 = t_filler.ljust(279)   
                            
                            payment_file_content += '04' + f_num_aviso + f_glosa_aviso + f_corr_aviso + f_filler_04 + '\n'
                            
                return (payment_file_content, f_file_name)

            else:
                raise UserError(_(
                "No file structure available for this payment method. Check "
                "supported payment methods and method name spelling."))

                return (False, False)
            

    @api.multi
    def open2generated(self):
        self.ensure_one()
        payment_file_str, filename = self.generate_payment_file()
        action = {}
        if payment_file_str and filename:
            attachment = self.env['ir.attachment'].create({
                'res_model': 'account.payment.order',
                'res_id': self.id,
                'name': filename,
                #'datas': base64.b64encode(payment_file_str),
                'datas': base64.b64encode(bytes(payment_file_str, 'utf-8')),
                'datas_fname': filename,
                })
            simplified_form_view = self.env.ref(
                'account_payment_order.view_attachment_simplified_form')
            action = {
                'name': _('Payment File'),
                'view_mode': 'form',
                'view_id': simplified_form_view.id,
                'res_model': 'ir.attachment',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': attachment.id,
                }
        self.write({
            'date_generated': fields.Date.context_today(self),
            'state': 'generated',
            'generated_user_id': self._uid,
            })
        return action

    @api.multi
    def generated2uploaded(self):
        for order in self:
            if order.payment_mode_id.generate_move:
                order.generate_move()
        self.write({
            'state': 'uploaded',
            'date_uploaded': fields.Date.context_today(self),
            })
        # Insert Intellego-BI: Marcar como hecho tras confirmar Upload
        self.write({'state': 'done'})
        return True

    @api.multi
    def _prepare_move(self, bank_lines=None):
        if self.payment_type == 'outbound':
            ref = _('Payment order %s') % self.name
        else:
            ref = _('Debit order %s') % self.name
        if bank_lines and len(bank_lines) == 1:
            ref += " - " + bank_lines.name
        if self.payment_mode_id.offsetting_account == 'bank_account':
            journal_id = self.journal_id.id
        elif self.payment_mode_id.offsetting_account == 'transfer_account':
            journal_id = self.payment_mode_id.transfer_journal_id.id
        vals = {
            'journal_id': journal_id,
            'ref': ref,
            'payment_order_id': self.id,
            'line_ids': [],
            }
        return vals

    @api.multi
    def _prepare_move_line_offsetting_account(
            self, amount_company_currency, amount_payment_currency,
            bank_lines):
        vals = {}
        if self.payment_type == 'outbound':
            name = _('Payment order %s') % self.name
        else:
            name = _('Debit order %s') % self.name
        if self.payment_mode_id.offsetting_account == 'bank_account':
            vals.update({'date': bank_lines[0].date})
        else:
            vals.update({'date_maturity': bank_lines[0].date})

        if self.payment_mode_id.offsetting_account == 'bank_account':
            account_id = self.journal_id.default_debit_account_id.id
        elif self.payment_mode_id.offsetting_account == 'transfer_account':
            account_id = self.payment_mode_id.transfer_account_id.id
        partner_id = False
        for index, bank_line in enumerate(bank_lines):
            if index == 0:
                partner_id = bank_line.payment_line_ids[0].partner_id.id
            elif bank_line.payment_line_ids[0].partner_id.id != partner_id:
                # we have different partners in the grouped move
                partner_id = False
                break
        vals.update({
            'name': name,
            'partner_id': partner_id,
            'account_id': account_id,
            'credit': (self.payment_type == 'outbound' and
                       amount_company_currency or 0.0),
            'debit': (self.payment_type == 'inbound' and
                      amount_company_currency or 0.0),
        })
        if bank_lines[0].currency_id != bank_lines[0].company_currency_id:
            sign = self.payment_type == 'outbound' and -1 or 1
            vals.update({
                'currency_id': bank_lines[0].currency_id.id,
                'amount_currency': amount_payment_currency * sign,
                })
        return vals

    @api.multi
    def _prepare_move_line_partner_account(self, bank_line):
        if bank_line.payment_line_ids[0].move_line_id:
            account_id =\
                bank_line.payment_line_ids[0].move_line_id.account_id.id
        else:
            if self.payment_type == 'inbound':
                account_id =\
                    bank_line.partner_id.property_account_receivable_id.id
            else:
                account_id =\
                    bank_line.partner_id.property_account_payable_id.id
        if self.payment_type == 'outbound':
            name = _('Payment bank line %s') % bank_line.name
        else:
            name = _('Debit bank line %s') % bank_line.name
        vals = {
            'name': name,
            'bank_payment_line_id': bank_line.id,
            'partner_id': bank_line.partner_id.id,
            'account_id': account_id,
            'credit': (self.payment_type == 'inbound' and
                       bank_line.amount_company_currency or 0.0),
            'debit': (self.payment_type == 'outbound' and
                      bank_line.amount_company_currency or 0.0),
            }

        if bank_line.currency_id != bank_line.company_currency_id:
            sign = self.payment_type == 'inbound' and -1 or 1
            vals.update({
                'currency_id': bank_line.currency_id.id,
                'amount_currency': bank_line.amount_currency * sign,
                })
        return vals

    @api.multi
    def generate_move(self):
        """
        Create the moves that pay off the move lines from
        the payment/debit order.
        """
        self.ensure_one()
        am_obj = self.env['account.move']
        post_move = self.payment_mode_id.post_move
        # prepare a dict "trfmoves" that can be used when
        # self.payment_mode_id.move_option = date or line
        # key = unique identifier (date or True or line.id)
        # value = bank_pay_lines (recordset that can have several entries)
        trfmoves = {}
        for bline in self.bank_line_ids:
            hashcode = bline.move_line_offsetting_account_hashcode()
            if hashcode in trfmoves:
                trfmoves[hashcode] += bline
            else:
                trfmoves[hashcode] = bline

        for hashcode, blines in trfmoves.items():
            mvals = self._prepare_move(blines)
            total_company_currency = total_payment_currency = 0
            for bline in blines:
                total_company_currency += bline.amount_company_currency
                total_payment_currency += bline.amount_currency
                partner_ml_vals = self._prepare_move_line_partner_account(
                    bline)
                mvals['line_ids'].append((0, 0, partner_ml_vals))
            trf_ml_vals = self._prepare_move_line_offsetting_account(
                total_company_currency, total_payment_currency, blines)
            mvals['line_ids'].append((0, 0, trf_ml_vals))
            move = am_obj.create(mvals)
            blines.reconcile_payment_lines()
            if post_move:
                move.post()


