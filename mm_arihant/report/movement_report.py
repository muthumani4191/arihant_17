# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools

STOCK_STATUS = [
    ('inward', 'Inward'),
    ('outward', 'Outward'),
]
MRP_STATUS = [
    ('internal', 'Production'),
    ('external', 'Sub Contracter'),
]

QC_STATUS = [
    ('good', 'Good'),
    ('scrap', 'Scrap'),
]

class SaleMovementReport(models.Model):
    _name = "sale.movement.report"
    _description = "Arihant Movement Report"
    _auto = False

    # sale.order fields
    name = fields.Char(string="Order Reference", readonly=True)
    sale_id = fields.Many2one(comodel_name='sale.order', string="Sale Order", readonly=True)
    sale_product_id = fields.Many2one(comodel_name='product.template', string="Sale Product", readonly=True)
    company_id = fields.Many2one(comodel_name='res.company', readonly=True)
    sale_qty = fields.Float('Sale Qty')
    raw_qty = fields.Float('Raw Material Qty')
    qty = fields.Float('Quantity')
    job_id = fields.Many2one(comodel_name='job.order', string="Job Order", readonly=True)
    purchase_id = fields.Many2one(comodel_name='purchase.order', string="Purchase Order", readonly=True)
    raw_id = fields.Many2one(comodel_name='product.product', string="Raw Material", readonly=True)
    progress_id = fields.Many2one(comodel_name='job.progress', string="Job Progress", readonly=True)
    flow_id = fields.Many2one(comodel_name='job.flow', string="Flow", readonly=True)
    type = fields.Selection(STOCK_STATUS, string="Type")
    mrp_type = fields.Selection(MRP_STATUS, string="Production Type")
    quality_type = fields.Selection(MRP_STATUS, string="Quality")


    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'sale_movement_report')
        self._cr.execute("""
            CREATE OR REPLACE VIEW sale_movement_report AS (
                SELECT so.id, so.id AS sale_id, so.company_id, sol.product_id AS sale_product_id ,sol.product_uom_qty AS sale_qty,
				jo.id AS job_id, po.id AS purchase_id,sm.product_id AS raw_id, sm.product_qty AS raw_qty,
				jp.id AS progress_id, jf.id AS flow_id,
				CASE WHEN ji.type = 'inward' THEN 'inward' ELSE 'outward' END AS type,
				CASE WHEN ji.mrp_type = 'internal' AND ji.type = 'outward' THEN 'internal' 
					 WHEN ji.mrp_type = 'external' AND ji.type = 'outward' THEN 'external' ELSE '' END AS mrp_type,
				CASE WHEN ji.quality_type = 'good' AND ji.type = 'inward' THEN 'good' 
					 WHEN ji.quality_type = 'scrap' AND ji.type = 'inward' THEN 'scrap' ELSE '' END AS quality_type,
				SUM(jil.product_qty) AS qty
				FROM sale_order so
				JOIN sale_order_line sol ON sol.order_id = sol.id
				JOIN job_order jo ON jo.sale_id = so.id
				JOIN purchase_order po ON po.job_id = jo.id
				JOIN purchase_order_line pol ON pol.order_id = po.id
				JOIN procurement_group pg ON pg.name = po.name
				JOIN stock_picking sp ON sp.group_id = pg.id AND sp.sale_id = so.id AND jo.id = sp.job_id
				JOIN stock_move sm ON sm.picking_id = sp.id
				LEFT JOIN job_progress jp ON jp.job_id = jo.id AND jp.sale_id = so.id
				LEFT JOIN job_flow jf ON jf.id = jp.flow_id
				LEFT JOIN job_inward ji ON ji.progress_id = jp.id AND ji.sale_id = so.id AND ji.sale_id = jp.sale_id AND ji.state = 'Done'
				LEFT JOIN job_inward_line jil ON jil.inward_id = ji.id 
				LEFT JOIN product_product ppf ON ppf.id = jil.product_id AND jf.product_id = ppf.id 
				WHERE so.id = 28 AND sp.state='done'
				GROUP BY so.id,sol.product_id,sol.product_uom_qty,jo.id,po.id,sm.product_id,sm.product_qty,jp.id,jf.id,type,mrp_type,quality_type
            )""")
