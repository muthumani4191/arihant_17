# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Arihant',
    'version': '1.2',
    'category': 'Arihant/Manufacturing',
    'summary': 'Sales for the product manufacturing on raw materials data',
    'description': """
This module contains all the common features of Sales Management and eCommerce.
    """,
    'depends': [
        'base',
        'sale',
        'sale_stock'
    ],
    'data': [
		'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/stock_delivery_inward_views.xml',
        #'security/ir_rules.xml',
        'views/master_views.xml',
        'views/job_order_views.xml',
        'views/progress_flow_views.xml',
        'views/inward_progress_views.xml',
        'report/movement_report_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'assets': {
        'web.assets_backend': [
        ],
        'web.assets_frontend': [
        ],
        'web.assets_tests': [
        ],
        'web.qunit_suite_tests': [
        ],
        'web.report_assets_common': [
        ],
    },
    'license': 'LGPL-3',
}
