# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError

TESTING_STATUS = [
    ('draft', 'Draft'),
    ('in_progress', 'In Progress'),
    ('Done', 'Completed'),
    ('Rejected', 'Rejected'),
    ('Cancelled', 'Cancelled')
]

MATERIAL_STATUS = [
    ('ok', 'OK'),
    ('Rejected', 'Rejected'),
]

FLOW_STATUS = [
    ('start', 'Start'),
    ('on_going', 'In Progress'),
    ('inspection', 'Inspection'),
    ('fg', 'FG'),
]

class TestingSheet(models.Model):
    _name = 'testing.sheet'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Testing Sheet"
    _order = 'name asc, id desc'
    _check_company_auto = True
     
    #=== FIELDS ===#
    name = fields.Char(string="Name",required=True)
    partner_id = fields.Many2one('res.partner','Vendor Name', readonly=False)
    company_id = fields.Many2one(comodel_name='res.company',required=True, index=True, default=lambda self: self.env.company)
    test_no = fields.Char('Test Report No', readonly=False)
    test_date = fields.Date('Test Report Date', readonly=False)
    material_status = fields.Selection(MATERIAL_STATUS, readonly=False)
    bill_no = fields.Char('Bill No', readonly=False)
    bill_date = fields.Date('Bill Date', readonly=False)
    test_dec = fields.Char("Crack Test", readonly=False)
    mechanical_no = fields.Char('Machanical Properties No', readonly=False)
    micro_no = fields.Char('Micro Report No', readonly=False)
    testing_person_id = fields.Many2one('res.partner','QC Approver', readonly=False)
    sale_id = fields.Many2one('sale.order', 'Sale')
    job_id = fields.Many2one('job.order', 'Job')
    job_no = fields.Char('Job No', readonly=False)
    job_date = fields.Date('Job Date', readonly=False)
    dc_no = fields.Char('DC No', readonly=False)
    dc_date = fields.Date('DC Date', readonly=False)
    testing_elements = fields.Char('Testing Elements', readonly=False)
    crack_testing = fields.Char('Crack Test', readonly=False)
    state = fields.Selection(TESTING_STATUS, required=True, string="Status", readonly=True, copy=False, index=True, tracking=3,default='draft')
    
    def open_testing(self):
        return self.write({'state':'in_progress'})
        
    def open_complete(self):
        return self.write({'state':'Done','material_status':'ok'})
        
    def open_rejected(self):
        return self.write({'state':'Rejected','material_status':'Rejected'})
        
   
class JobFlow(models.Model):
    _name = 'job.flow'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Job Flow"
    _order = 'sequence asc'
    _check_company_auto = True
    
    name = fields.Char(string="Name",required=True)
    code = fields.Char(string="Code",required=True)
    company_id = fields.Many2one(comodel_name='res.company',required=True, index=True, default=lambda self: self.env.company)
    sequence = fields.Integer('Sequence')
    code_status = fields.Selection(FLOW_STATUS, required=True)
    product_id = fields.Many2one('product.product', 'Product', required=True)
    active = fields.Boolean('Active', default=True)
