# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError

JOB_STATUS = [
    ('draft', 'Draft'),
    ('configure', 'Configure'),
    ('in_progress', 'In Progress'),
    ('Done', 'Completed'),
    ('Rejected', 'Rejected'),
    ('Cancelled', 'Cancelled')
]

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_raw_line = fields.One2many('product.raw.line', 'raw_id', 'Product')

class ProductRawLine(models.Model):
    _name = 'product.raw.line'
    _description = "Raw Line"

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    raw_id = fields.Many2one('product.template', 'BOM')
    name = fields.Char('Name')
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null',domain="[('purchase_ok', '=', True)]")
    product_qty = fields.Float('Quantity', default=1.0, digits='Percentage Analytic', required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Uom', default=_get_default_product_uom_id,required=True)


    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.product_tmpl_id.uom_po_id.id

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    job_id = fields.Many2one('job.order', 'Job Number')
    jh_no = fields.Char('JH No', readonly=False)

    @api.onchange('job_id')
    def onchange_job_id(self):
        if self.job_id:
            self.jh_no = self.job_id.jh_no


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sale_id = fields.Many2one('sale.order', 'Sale')
    job_id = fields.Many2one('job.order', 'Job')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('job_count')
    def _compute_job_ids(self):
        for order in self:
            order.job_count = len([job.id for job in self.env['job.order'].search([('sale_id','=',order.id)])])

    @api.depends('purchase_count')
    def _compute_purchase_ids(self):
        for order in self:
            order.purchase_count = len([job.id for job in self.env['purchase.order'].search([('sale_id','=',order.id)])])

    @api.depends('picking_ids')
    def _compute_picking_ids(self):
        for order in self:
            order.delivery_count = len([job.id for job in self.env['stock.picking'].search([('sale_id','=',order.id),('origin','=',order.name)])])

    job_count = fields.Integer(string='Job Orders', compute='_compute_job_ids')
    purchase_count = fields.Integer(string='Purchase Orders', compute='_compute_purchase_ids')

    def action_confirm(self):
        res = super().action_confirm()
        count = 1
        for line in self.order_line:
            val = {
            'name':'JOB'+str(count).zfill(2),
            'job_number':self.env['ir.sequence'].next_by_code('job.order') or _("New"),
            'company_id':line.company_id.id,
            'sale_id':self.id,
            'product_id':line.product_id.id,
            'product_uom_qty':line.product_uom_qty,
            'state':'draft'
            }
            job = self.env['job.order'].create(val)
            for raw_data in line.product_id.product_tmpl_id.product_raw_line:
                val_line = {
                'bom_id':job.id,
                'product_id':raw_data.product_id.id,
                'product_qty':raw_data.product_qty,
                'product_uom_id':raw_data.product_uom_id.id,
                'customer_qty':line.product_uom_qty,
                }
                self.env['job.bom.line'].create(val_line)
            count = count + 1
            data = self.env['job.flow'].search([('id','>',0)], order="sequence ASC")
            for rec in data:
                val = {
                'bom_id':job.id,
                'flow_id':rec.id,
                'name':rec.name,
                'included':True,
                }
                self.env['job.process.line'].create(val)
        return res

    def action_view_job(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env["ir.actions.actions"]._for_xml_id("mm_arihant.action_job_order")
        job_ids = [job.id for job in self.env['job.order'].search([('sale_id','=',self.id)])]

        if len(job_ids) > 1:
            action['domain'] = [('id', 'in', job_ids)]
        elif job_ids:
            form_view = [(self.env.ref('mm_arihant.view_job_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = job_ids[0]
        # Prepare the context.
        picking_id = job_ids[0] if len(job_ids) == 1 else 0
        job_id = self.env['job.order'].browse(picking_id)
        action['context'] = dict(self._context, default_sale_id=self.id)
        return action

    def action_view_purchase(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_form_action")
        purchase_ids = [job.id for job in self.env['purchase.order'].search([('sale_id','=',self.id)])]

        if len(purchase_ids) > 1:
            action['domain'] = [('id', 'in', purchase_ids)]
        elif purchase_ids:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = purchase_ids[0]
        # Prepare the context.
        picking_id = purchase_ids[0] if len(purchase_ids) == 1 else 0
        purchase_id = self.env['purchase.order'].browse(picking_id)
        action['context'] = dict(self._context, default_sale_id=self.id)
        return action

    def _get_action_view_picking(self, pickings):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        pickings = [job.id for job in self.env['stock.picking'].search([('sale_id','=',self.id),('origin','=',self.name)])]

        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            picking_id = self.env['stock.picking'].browse(pickings[0])
            action['res_id'] = picking_id.id
        # Prepare the context.
        picking_id = 0
        if len(pickings) == 1:
            picking_id = self.env['stock.picking'].browse(pickings[0])
        action['context'] = dict(self._context, default_partner_id=self.partner_id.id, default_picking_type_id=picking_id.picking_type_id.id, default_origin=self.name, default_group_id=picking_id.group_id.id)
        return action

    def action_purchase_create(self):
        query_partner = """
        SELECT DISTINCT ps.partner_id
        FROM job_order jo
        JOIN job_bom_line jbl ON jbl.bom_id = jo.id
        JOIN product_product pp ON pp.id = jbl.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_supplierinfo ps ON pt.id = ps.product_tmpl_id
        WHERE jo.sale_id = %s
        GROUP BY jbl.product_id, ps.partner_id """
        self._cr.execute(query_partner, [self.id])
        for values in self._cr.dictfetchall():
            val = {
            'partner_id':values['partner_id'],
            'sale_id':self.id
            }
            purchase = self.env['purchase.order'].create(val)
            query_product = """
            SELECT jbl.product_id, jbl.product_uom_id, SUM(jbl.product_qty * jo.product_uom_qty) AS qty
            FROM job_order jo
            JOIN job_bom_line jbl ON jbl.bom_id = jo.id
            JOIN product_product pp ON pp.id = jbl.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_supplierinfo ps ON pt.id = ps.product_tmpl_id
            WHERE jo.sale_id = %s AND ps.partner_id = %s
            GROUP BY jbl.product_id, product_uom_id """
            self._cr.execute(query_product, [self.id, values['partner_id']])
            for line in self._cr.dictfetchall():
                val_line = {
                'product_id':line['product_id'],
                'order_id':purchase.id,
                'product_qty':line['qty'],
                'product_uom':line['product_uom_id'],
                }
                self.env['purchase.order.line'].create(val_line)

        return True

class JobOrder(models.Model):
    _name = 'job.order'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Job Order"
    _order = 'sale_id asc, name asc'
    _check_company_auto = True

    _sql_constraints = [
        ('unique_name', 'unique (jh_no)', 'The JH NO must be unique!')
    ]

    @api.depends('testing_count')
    def _compute_testing_ids(self):
        for order in self:
            order.testing_count = len([job.id for job in self.env['testing.sheet'].search([('sale_id','=',order.sale_id.id), ('job_id','=',order.id)])])

    @api.depends('picking_count')
    def _compute_picking_ids(self):
        for order in self:
            order.picking_count = len([job.id for job in self.env['stock.picking'].search([('sale_id','=',order.sale_id.id), ('job_id','=',order.id)])])

    @api.depends('purchase_count')
    def _compute_purchase_ids(self):
        for order in self:
            order.purchase_count = len([job.id for job in self.env['purchase.order'].search([('job_id','=',order.id)])])

    @api.depends('progress_count')
    def _compute_progress_ids(self):
        for order in self:
            order.progress_count = len([job.id for job in self.env['job.progress'].search([('job_id','=',order.id),('sale_id','=',order.sale_id.id)])])

    @api.depends('job_bom_line','product_uom_qty')
    def _compute_required_qty(self):
        required_qty = 0.0
        for order in self:
            dia_qty = 0.0
            for qty in order.job_bom_line:
                dia_qty += qty.product_qty
            order.required_qty += dia_qty * order.product_uom_qty


    #=== FIELDS ===#
    name = fields.Char(string="Name",required=True)
    job_number = fields.Char('Job Number', readonly=True)
    job_date = fields.Date('Job Date', readonly=False)
    company_id = fields.Many2one(comodel_name='res.company',required=True, index=True, default=lambda self: self.env.company)
    sale_id = fields.Many2one('sale.order',string="Sale")
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null',domain="[('sale_ok', '=', True)]", required=True, readonly=False)
    product_uom_qty = fields.Float(string="Quantity",digits='Product Unit of Measure', default=1.0,store=True, readonly=False, required=True)
    jh_no = fields.Char('JH No', readonly=False)
    drawing_no = fields.Char('Drawing no', readonly=False)
    yeild_per = fields.Integer('Yeild %', readonly=False)
    fg_exp_date = fields.Date('Expected FG Date', readonly=False)
    actual_date = fields.Date('Actual Date', readonly=False)
    state = fields.Selection(JOB_STATUS, required=True, string="Status", readonly=True, copy=False, index=True, tracking=3,default='draft')
    product_qty = fields.Float('Qty', default=1.0, digits='Product Unit of Measure', required=True, help="Below mentioned BOM kgs belonge to this Qty")
    required_qty = fields.Float('Required Kgs', default=0.0, digits='Percentage Analytic', compute='_compute_required_qty', required=True, help="Below mentioned BOM kgs belonge to this Qty")
    job_bom_line = fields.One2many('job.bom.line', 'bom_id','BOM Line')
    job_process_line = fields.One2many('job.process.line', 'bom_id','BOM Line')
    flow_cycle_line = fields.One2many('flow.cycle.line', 'bom_id','BOM Line')
    testing_count = fields.Integer(string='Testing', compute='_compute_testing_ids')
    picking_count = fields.Integer(string='Picking', compute='_compute_picking_ids')
    purchase_count = fields.Integer(string='Purchase Orders', compute='_compute_purchase_ids')
    progress_count = fields.Integer(string='Purchase Orders', compute='_compute_progress_ids')

    def open_configure(self):
        cycle_data = [cycle.flow_id.id for cycle in self.job_process_line if cycle.included == True]
        for i in range(len(cycle_data) - 1):
            cycle = {
            'bom_id':self.id,
            'flow_start_id':cycle_data[i],
            'flow_end_id':cycle_data[i + 1],
            }
            self.env['flow.cycle.line'].create(cycle)
        return self.write({'state':'configure'})

    def create_progres(self):
        for line in self.job_process_line:
            if line.included == True:
                val = {
                'name':line.flow_id.name,
                'state':'draft',
                'job_id':self.id,
                'sale_id':self.sale_id.id,
                'flow_id':line.flow_id.id,
                'flow_type':line.flow_id.code_status,
                'jh_no':self.jh_no,
                'product_id':self.product_id.id,
                'product_uom_qty':self.product_uom_qty,
                'raw_uom_qty':self.required_qty,
                }
                self.env['job.progress'].create(val)
        return self.write({'state':'in_progress'})


    def create_testing(self):
        val = {
        'name':self.env['ir.sequence'].next_by_code('TESTING.SHEET') or _("New"),
        'state':'draft',
        'sale_id':self.sale_id.id,
        'job_id':self.id,
        'job_no':self.job_number,
        'job_date':self.job_date,
        }
        self.env['testing.sheet'].create(val)
    def action_view_testing(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mm_arihant.action_testing_sheet")
        testing_ids = [job.id for job in self.env['testing.sheet'].search([('sale_id','=',self.sale_id.id),('job_id','=',self.id)])]

        if len(testing_ids) > 1:
            action['domain'] = [('id', 'in', testing_ids)]
        elif testing_ids:
            form_view = [(self.env.ref('mm_arihant.testing_sheet_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = testing_ids[0]
        # Prepare the context.
        picking_id = testing_ids[0] if len(testing_ids) == 1 else 0
        testing_id = self.env['testing.sheet'].browse(picking_id)
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id=self.id)
        return action

    def action_view_picking(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        pickings = [job.id for job in self.env['stock.picking'].search([('sale_id','=',self.sale_id.id),('job_id','=',self.id)])]

        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            picking_id = self.env['stock.picking'].browse(pickings[0])
            action['res_id'] = picking_id.id
        ## Prepare the context.
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id_id=self.id)
        return action

    def create_purchase(self):
        query_partner = """
        SELECT DISTINCT ps.partner_id
        FROM job_order jo
        JOIN job_bom_line jbl ON jbl.bom_id = jo.id
        JOIN product_product pp ON pp.id = jbl.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_supplierinfo ps ON pt.id = ps.product_tmpl_id
        WHERE jo.id = %s
        GROUP BY jbl.product_id, ps.partner_id """
        self._cr.execute(query_partner, [self.id])
        for values in self._cr.dictfetchall():
            val = {
            'partner_id':values['partner_id'],
            'sale_id':self.sale_id.id,
            'job_id':self.id
            }
            purchase = self.env['purchase.order'].create(val)
            query_product = """
            SELECT jbl.product_id, jbl.product_uom_id, SUM(jbl.product_qty * jo.product_uom_qty) AS qty
            FROM job_order jo
            JOIN job_bom_line jbl ON jbl.bom_id = jo.id
            JOIN product_product pp ON pp.id = jbl.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_supplierinfo ps ON pt.id = ps.product_tmpl_id
            WHERE jo.id = %s AND ps.partner_id = %s
            GROUP BY jbl.product_id, product_uom_id """
            self._cr.execute(query_product, [self.id, values['partner_id']])
            for line in self._cr.dictfetchall():
                val_line = {
                'product_id':line['product_id'],
                'order_id':purchase.id,
                'product_qty':line['qty'],
                'product_uom':line['product_uom_id'],
                }
                self.env['purchase.order.line'].create(val_line)

        return True

    def action_view_purchase(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_form_action")
        purchase_ids = [job.id for job in self.env['purchase.order'].search([('job_id','=',self.id)])]

        if len(purchase_ids) > 1:
            action['domain'] = [('id', 'in', purchase_ids)]
        elif purchase_ids:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = purchase_ids[0]
        # Prepare the context.
        picking_id = purchase_ids[0] if len(purchase_ids) == 1 else 0
        purchase_id = self.env['purchase.order'].browse(picking_id)
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id=self.id,default_jh_no=self.jh_no)
        return action

    def action_view_progress(self):
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        action = self.env["ir.actions.actions"]._for_xml_id("mm_arihant.action_job_progress")
        progress_ids = [job.id for job in self.env['job.progress'].search([('job_id','=',self.id), ('sale_id','=',self.sale_id.id)])]

        if len(progress_ids) > 1:
            action['domain'] = [('id', 'in', progress_ids)]
        elif progress_ids:
            form_view = [(self.env.ref('mm_arihant.job_progress_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = progress_ids[0]
        action['context'] = dict(self._context, default_sale_id=self.sale_id.id, default_job_id=self.id,default_jh_no=self.jh_no)
        return action

class JobBomLine(models.Model):
    _name = 'job.bom.line'
    _description = "BOM Line"

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    @api.depends('customer_qty','required_qty')
    def _compute_required_qty(self):
        for line in self:
            line.required_qty = line.customer_qty * line.product_qty

    bom_id = fields.Many2one('job.order', 'BOM')
    name = fields.Char('Name')
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null',domain="[('purchase_ok', '=', True)]")
    product_qty = fields.Float('Quantity', default=1.0, digits='Percentage Analytic', required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Uom', default=_get_default_product_uom_id,required=True)
    customer_qty = fields.Float('Customer Qty', default=1.0, digits='Percentage Analytic', required=True)
    required_qty = fields.Float('Required Kgs', default=0.0, digits='Percentage Analytic', compute='_compute_required_qty', required=True, help="Below mentioned BOM kgs belonge to this Qty")


    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.product_tmpl_id.uom_po_id.id


class JobProcessLine(models.Model):
    _name = 'job.process.line'
    _description = "Job Process Line"

    bom_id = fields.Many2one('job.order', 'BOM')
    name = fields.Char('Name')
    flow_id = fields.Many2one('job.flow', 'Flow')
    included = fields.Boolean('Included')

class FlooCycleLine(models.Model):
    _name = 'flow.cycle.line'
    _description = "Flow Cycle Line"

    bom_id = fields.Many2one('job.order', 'BOM')
    name = fields.Char('Name')
    flow_start_id = fields.Many2one('job.flow', 'Flow Start')
    flow_end_id = fields.Many2one('job.flow', 'Flow End')


