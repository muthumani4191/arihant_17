# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError

FLOW_STATUS = [
    ('draft', 'Draft'),
    ('in_progress', 'In Progress'),
    ('production', 'Production'),
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

STOCK_STATUS = [
    ('inward', 'Inward'),
    ('outward', 'Outward'),
]
MRP_STATUS = [
    ('internal', 'Internal'),
    ('external', 'Sub Contracter'),
]

HT_STATUS = [
    ('normalizing', 'Normalizing'),
    ('annesling', 'Annesling'),
    ('Hardening_temp', 'Hardening & Tempering'),
]

QC_STATUS = [
    ('good', 'Good'),
    ('scrap', 'Scrap'),
]

class JobInward(models.Model):
    _name = 'job.inward'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Job Inward"
    _order = 'id asc'
    _check_company_auto = True
     
    #=== FIELDS ===#
    name = fields.Char(string="Name",required=True)
    company_id = fields.Many2one(comodel_name='res.company',required=True, index=True, default=lambda self: self.env.company)
    state = fields.Selection(FLOW_STATUS, required=True, string="Status", readonly=True, copy=False, index=True, tracking=3,default='draft')
    
    job_id = fields.Many2one('job.order', 'Job Number')
    progress_id = fields.Many2one('job.progress', 'Job Progress')
    sale_id = fields.Many2one('sale.order',string="Sale")
    dc_date = fields.Date('Date', default=fields.Datetime.now)
    flow_id = fields.Many2one('job.flow', 'Flow')
    flow_type = fields.Selection(JOB_STATUS, string="Flow Status")
    ht_type = fields.Selection(HT_STATUS, string="HT Process")
    required_date = fields.Date(string="Required Date")
    required_hardness = fields.Char(string="Required Hardness")
    ht_report_number = fields.Char(string="HT Report No")
    micro_report_number = fields.Char(string="Micro Report No")
    flow_code = fields.Char(string="Flow Code")
    type = fields.Selection(STOCK_STATUS, string="Type")
    quality_type = fields.Selection(QC_STATUS, string="Quality Type")
    jh_no = fields.Char('JH No', readonly=False)
    partner_id = fields.Many2one('res.partner','Vendor Name', readonly=False)
    mrp_type = fields.Selection(MRP_STATUS, string="Contract Type", required=True)
    receipt_no = fields.Char('Receipt Number', required=True)
    job_inward_line = fields.One2many('job.inward.line', 'inward_id','BOM Line')
    
    def complete_production(self):
        return self.write({'state':'Done'})
    
    
class JobInwardLine(models.TransientModel):
    _name = 'job.inward.line'
    _description = "Job Inward Line"

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    inward_id = fields.Many2one('job.inward', 'Delivery')
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null',domain="[('purchase_ok', '=', True)]")
    product_qty = fields.Float('Quantity', default=1.0, digits='Percentage Analytic', required=True)
    received_qty = fields.Float('Received Qty', default=0.0, digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Uom', default=_get_default_product_uom_id,required=True)
