# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError

FLOW_STATUS = [
    ('draft', 'Draft'),
    ('in_progress', 'In Progress'),
    ('Done', 'Completed'),
    ('Rejected', 'Rejected'),
    ('Cancelled', 'Cancelled')
]
JOB_STATUS = [
    ('start', 'Start'),
    ('on_going', 'In Progress'),
    ('inspection', 'Inspection'),
    ('fg', 'FG'),
]
class JobProgress(models.Model):
    _name = 'job.progress'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Job Progress"
    _order = 'id asc'
    _check_company_auto = True

    @api.depends('dc_count')
    def _compute_dc_count(self):
        for order in self:
            order.dc_count = len([job.id for job in self.env['job.inward'].search([('job_id','=',order.job_id.id),('type','=','outward'),('progress_id','=',order.id),('mrp_type','=','external')])])

    @api.depends('prd_count')
    def _compute_production_count(self):
        for order in self:
            order.prd_count = len([job.id for job in self.env['job.inward'].search([('job_id','=',order.job_id.id),('type','=','outward'),('progress_id','=',order.id),('mrp_type','=','internal')])])

    @api.depends('prd_inprogress')
    def _compute_production_progress_count(self):
        for order in self:
            order.prd_inprogress = len([job.id for job in self.env['job.inward'].search([('job_id','=',order.job_id.id),('type','=','outward'),('progress_id','=',order.id),('mrp_type','=','internal'),('state','!=','Done')])])

    @api.depends('prd_completed')
    def _compute_production_complete_count(self):
        for order in self:
            order.prd_completed = len([job.id for job in self.env['job.inward'].search([('job_id','=',order.job_id.id),('type','=','outward'),('progress_id','=',order.id),('mrp_type','=','internal'),('state','=','Done')])])

    @api.depends('receipt_count')
    def _compute_receipt_count(self):
        for order in self:
            order.receipt_count = len([job.id for job in self.env['job.inward'].search([('job_id','=',order.job_id.id),('type','=','inward'),('progress_id','=',order.id),('quality_type','=','good')])])

    @api.depends('scrap_count')
    def _compute_scrap_count(self):
        for order in self:
            order.scrap_count = len([job.id for job in self.env['job.inward'].search([('job_id','=',order.job_id.id),('type','=','inward'),('progress_id','=',order.id),('quality_type','=','scrap')])])

    @api.depends('delivery_uom_qty')
    def _compute_delivery_qty(self):
        for order in self:
            delivery_qty = 0.0
            data = self.env['job.inward'].search([('progress_id','=',order.id),('type','=','outward'),('mrp_type','=','external')])
            for line in data.job_inward_line:
                delivery_qty += line.product_qty
            order.delivery_uom_qty = delivery_qty
            
    @api.depends('prd_in_uom_qty')
    def _compute_prd_in_qty(self):
        for order in self:
            delivery_qty = 0.0
            data = self.env['job.inward'].search([('progress_id','=',order.id),('type','=','outward'),('mrp_type','=','internal'),('state','!=','Done')])
            for line in data.job_inward_line:
                delivery_qty += line.product_qty
            order.prd_in_uom_qty = delivery_qty

    @api.depends('prd_out_uom_qty')
    def _compute_prd_done_qty(self):
        for order in self:
            delivery_qty = 0.0
            data = self.env['job.inward'].search([('progress_id','=',order.id),('type','=','outward'),('mrp_type','=','internal'),('state','=','Done')])
            for line in data.job_inward_line:
                delivery_qty += line.product_qty
            order.prd_out_uom_qty = delivery_qty

    @api.depends('received_uom_qty')
    def _compute_receipt_qty(self):
        for order in self:
            delivery_qty = 0.0
            data = self.env['job.inward'].search([('progress_id','=',order.id),('type','=','inward'),('quality_type','=','good')])
            for line in data.job_inward_line:
                delivery_qty += line.product_qty
            order.received_uom_qty = delivery_qty

    @api.depends('scrap_uom_qty')
    def _compute_scrap_qty(self):
        for order in self:
            delivery_qty = 0.0
            data = self.env['job.inward'].search([('progress_id','=',order.id),('type','=','inward'),('quality_type','=','scrap')])
            for line in data.job_inward_line:
                delivery_qty += line.product_qty
            order.scrap_uom_qty = delivery_qty

    @api.depends('cutting_size')
    def _compute_cutting_size(self):
        for order in self:
            order.cutting_size = order.raw_uom_qty / order.product_uom_qty

    #=== FIELDS ===#
    name = fields.Char(string="Name",required=True)
    company_id = fields.Many2one(comodel_name='res.company',required=True, index=True, default=lambda self: self.env.company)
    state = fields.Selection(FLOW_STATUS, required=True, string="Status", readonly=True, copy=False, index=True, tracking=3,default='draft')

    job_id = fields.Many2one('job.order', 'Job Number')
    sale_id = fields.Many2one('sale.order',string="Sale")
    flow_id = fields.Many2one('job.flow', 'Progress Name')
    flow_type = fields.Selection(JOB_STATUS, string="Flow Status")
    jh_no = fields.Char('JH No', readonly=False)
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null',domain="[('sale_ok', '=', True)]", required=True, readonly=False)
    product_uom_qty = fields.Float(string="Quantity",digits='Product Unit of Measure', default=1.0,store=True, readonly=False, required=True)
    delivery_uom_qty = fields.Float(string="Deliveried Qty",digits='Percentage Analytic', compute='_compute_delivery_qty')
    prd_in_uom_qty = fields.Float(string="In-Progress Qty",digits='Product Unit of Measure', compute='_compute_prd_in_qty')
    prd_out_uom_qty = fields.Float(string="Completed Qty",digits='Product Unit of Measure', compute='_compute_prd_done_qty')
    received_uom_qty = fields.Float(string="Received Qty",digits='Product Unit of Measure', compute='_compute_receipt_qty')
    scrap_uom_qty = fields.Float(string="Scrap Qty",digits='Product Unit of Measure', compute='_compute_scrap_qty')
    raw_uom_qty = fields.Float(string="Raw Material Kgs",digits='Percentage Analytic', default=1.0,readonly=False, required=True)
    dc_count = fields.Integer(string='Delivery Count', compute='_compute_dc_count')
    receipt_count = fields.Integer(string='Receipt Count', compute='_compute_receipt_count')
    scrap_count = fields.Integer(string='Scrap Count', compute='_compute_scrap_count')
    prd_count = fields.Integer(string='Production Count', compute='_compute_production_count')
    prd_inprogress = fields.Integer(string='Production Inprogress Count', compute='_compute_production_progress_count')
    prd_completed = fields.Integer(string='Production Completed Count', compute='_compute_production_complete_count')
    cutting_size = fields.Float('Cutting Size Kgs', digits='Percentage Analytic', default=0.0, compute='_compute_cutting_size')

    def open_progress(self):
        return self.write({'state':'in_progress'})

    def action_view_outward(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mm_arihant.action_job_inward")
        outward_ids = [job.id for job in self.env['job.inward'].search([('job_id','=',self.job_id.id),('type','=','outward'),('progress_id','=',self.id),('mrp_type','=','external')])]

        if len(outward_ids) > 1:
            action['domain'] = [('id', 'in', outward_ids)]
        elif outward_ids:
            form_view = [(self.env.ref('mm_arihant.job_inward_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = outward_ids[0]
        # Prepare the context.
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id=self.id,default_type='outward')
        return action

    def action_view_production(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mm_arihant.action_job_production")
        outward_ids = [job.id for job in self.env['job.inward'].search([('job_id','=',self.job_id.id),('type','=','outward'),('progress_id','=',self.id),('mrp_type','=','internal')])]

        if len(outward_ids) > 1:
            action['domain'] = [('id', 'in', outward_ids)]
        elif outward_ids:
            form_view = [(self.env.ref('mm_arihant.job_inward_production_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = outward_ids[0]
        # Prepare the context.
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id=self.id,default_type='outward')
        return action

    def action_view_inward(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mm_arihant.action_job_received")
        outward_ids = [job.id for job in self.env['job.inward'].search([('job_id','=',self.job_id.id),('type','=','inward'),('progress_id','=',self.id),('quality_type','=','good')])]

        if len(outward_ids) > 1:
            action['domain'] = [('id', 'in', outward_ids)]
        elif outward_ids:
            form_view = [(self.env.ref('mm_arihant.job_inward_receipt_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = outward_ids[0]
        # Prepare the context.
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id=self.id,default_type='inward',default_quality_type='good')
        return action

    def action_view_scrap(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mm_arihant.action_job_scrap")
        outward_ids = [job.id for job in self.env['job.inward'].search([('job_id','=',self.job_id.id),('type','=','inward'),('progress_id','=',self.id),('quality_type','=','scrap')])]

        if len(outward_ids) > 1:
            action['domain'] = [('id', 'in', outward_ids)]
        elif outward_ids:
            form_view = [(self.env.ref('mm_arihant.job_inward_scrap_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = outward_ids[0]
        # Prepare the context.
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id=self.id,default_type='inward',default_quality_type='scrap')
        return action





