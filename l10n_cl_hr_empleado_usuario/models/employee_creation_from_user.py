# -*- coding: utf-8 -*-
###################################################################################
#
#    Intellego-BI.com
#    Copyright (C) 2017-TODAY Intellego Business Intelligence S.A.(<http://www.intellego-bi.com>).
#    Author: Rodolfo Bermúdez Neubauer(<https://www.intellego-bi.com>)
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
###################################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import re


class ResUsersInherit(models.Model):
    _inherit = 'res.users'

    identification_id = fields.Char(string='Identification No')

    user_type = fields.Selection([('inte', 'Internal'), ('empl', 'Employee')], string='User Type', default='inte')
    type_id = fields.Many2one('hr.type.employee', 'Tipo de Empleado')
    department_id = fields.Many2one('hr.department', string='Department')
    country_id = fields.Many2one('res.country', 'Nationality (Country)')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], default="male")

    firstname = fields.Char("Firstname")
    last_name = fields.Char("Last Name")
    middle_name = fields.Char("Middle Name", help='Employees middle name')
    mothers_name = fields.Char("Mothers Name", help='Employees mothers name')

    employee_id = fields.Many2one('hr.employee',
                                  string='Related Employee', ondelete='restrict', auto_join=True,
                                  help='Employee-related data of the user')

    @api.model
    def _get_computed_name(self, last_name, firstname, mothers_name=None, middle_name=None):
        names = list()
        if firstname:
            names.append(firstname)
        if middle_name:
            names.append(middle_name)
        if last_name:
            names.append(last_name)
        if mothers_name:
            names.append(mothers_name)

        return " ".join(names)

    @api.multi
    @api.onchange('firstname', 'mothers_name', 'middle_name', 'last_name')
    def get_name(self):
        for user in self:
            if user.firstname and user.last_name:
                user.name = self._get_computed_name(
                    user.last_name, user.firstname, user.mothers_name, user.middle_name)

    @api.onchange('identification_id')
    def onchange_document(self):
        identification_id = (
            re.sub('[^1234567890Kk]', '',
            str(self.identification_id))).zfill(9).upper()

        self.identification_id = '%s.%s.%s-%s' % (
            identification_id[0:2], identification_id[2:5], identification_id[5:8],
            identification_id[-1])

            
    @api.onchange('user_type', 'partner_id')
    def update_partner_as_employee(self):
        check_id = self.id
        bool_emp = True
        bool_int = False
        lati = '-33.30647'
        long = '-70.71494'
        cl_vat = ('CL' + 
            re.sub('[^1234567890Kk]', '',
            str(self.identification_id))).zfill(9).upper()
        if self.partner_id:
            check_id = self.partner_id.id
            partner_ids = self.env['res.partner'].search([
                              ('id', '=', check_id)])
            if len(partner_ids) == 1:
                for partner in partner_ids:
                    if self.user_type == 'empl':
                        if 'document_number' in self.env['res.partner']._fields:
                            if 'partner_latitude' in self.env['res.partner']._fields:
                                self.partner_id.write({'employee': bool_emp, 
                                                       'country_id': self.country_id.id,
                                                       'document_number': self.identification_id, 
                                                       'vat': cl_vat, 
                                                       'ref': self.identification_id,
                                                       'partner_latitude': lati,
                                                       'partner_longitude': long})
                            else:
                                self.partner_id.write({'employee': bool_emp, 
                                                       'country_id': self.country_id.id,
                                                       'document_number': self.identification_id, 
                                                       'vat': cl_vat, 
                                                       'ref': self.identification_id})
                            
                        else:
                            if 'partner_latitude' in self.env['res.partner']._fields:
                                self.partner_id.write({'employee': bool_emp, 
                                                       'country_id': self.country_id.id, 
                                                       'vat': cl_vat, 
                                                       'ref': self.identification_id,
                                                       'partner_latitude': lati,
                                                       'partner_longitude': long})
                            else:
                                self.partner_id.write({'employee': bool_emp, 
                                                       'country_id': self.country_id.id, 
                                                       'vat': cl_vat, 
                                                       'ref': self.identification_id})
                        return
                    else:
                        if 'document_number' in self.env['res.partner']._fields:
                            self.partner_id.write({'employee': bool_int, 
                                                   'country_id': self.country_id.id, 
                                                   'document_number': self.identification_id, 
                                                   'vat': cl_vat})
                        else:
                            self.partner_id.write({'employee': bool_int, 
                                                   'country_id': self.country_id.id, 
                                                   'vat': cl_vat})
                        return
            else:
                raise UserError(_('Se han encontrado %s partners') % (len(partner_ids)))
 

    @api.model
    def create(self, vals):
        """This code is to create an employee while creating an user."""
        vals['name'] = self._get_computed_name(
                    vals['last_name'], vals['firstname'], vals['mothers_name'], vals['middle_name'])
        result = super(ResUsersInherit, self).create(vals)
        work_email = ''
        if set(result['login']).issubset('@.'):
            work_email = result['login']

        result['employee_id'] = self.env['hr.employee'].sudo().create({'name': result['name'],
                                                                       'user_id': result['id'],
                                                                       'work_email': work_email,
                                                                       'firstname': vals['firstname'],
                                                                       'middle_name': vals['middle_name'],
                                                                       'last_name': vals['last_name'],
                                                                       'mothers_name': vals['mothers_name'],
                                                                       'type_id': vals['type_id'],
                                                                       'gender': vals['gender'],
                                                                       'country_id': vals['country_id'],
                                                                       'tz': 'America/Santiago',
                                                                       'department_id': vals['department_id'],
                                                                       'identification_id': vals['identification_id'],
                                                                       'formated_vat': vals['identification_id'],
                                                                       'address_home_id': result['partner_id'].id})
        
        
        return result



