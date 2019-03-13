# -*- coding: utf-8 -*-
# © 2019 Intellego-BI (www.intellego-bi.com)
# © 2010-2016 Akretion (www.akretion.com)
# © 2014 Tecnativa - Pedro M. Baeza
# © 2016 Tecnativa - Antonio Espinosa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Chile - Account Banking Credit Transfer',
    'summary': 'Create CSV files for Credit Transfers for Chilean Banks',
    'version': '12.0.1.0.0',
    'license': 'AGPL-3',
    'author': "Intellego-BI.com, "
              "Akretion, "
              "Tecnativa, "
              "Odoo Community Association (OCA)",
    'website': 'https://github.com/intellego-bi/odoo-cl-12',
    'category': 'Banking addons',
    'conflicts': ['account_sepa'],
    'depends': ['l10n_cl_pagos'],
    'data': [
        'data/account_payment_method.xml',
    ],
#    'demo': [
#        'demo/cl_credit_transfer_demo.xml'
#    ],
#    'post_init_hook': 'update_bank_journals',
    'installable': True,
}
