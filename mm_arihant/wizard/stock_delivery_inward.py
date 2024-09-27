# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

JOB_STATUS = [
    ('start', 'Start'),
    ('on_going', 'In Progress'),
    ('inspection', 'Inspection'),
    ('fg', 'FG'),
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

class StockDelivery(models.TransientModel):
    _name = 'stock.delivery'
    _inherit = 'mail.composer.mixin'
    _description = "Stock Delivery"

    name = fields.Char("Name")
    progress_id = fields.Many2one('job.progress', default=lambda self: self.env.context.get('active_id'))
    raw_uom_qty = fields.Float('Raw Material Kgs', compute='_compute_raw_uom_qty')
    flow_type = fields.Selection(JOB_STATUS, string="Flow Status", compute='_compute_flow_type', store=True)
    flow_code = fields.Char(string="Flow Code", compute='_compute_flow_code')
    job_raw_line = fields.One2many('stock.raw.line', 'delivery_id','BOM Line')
    mrp_type = fields.Selection(MRP_STATUS, string="Contract Type", required=True)
    dc_date = fields.Date('DC Date', default=fields.Datetime.now)
    ht_type = fields.Selection(HT_STATUS, string="HT Process")
    required_hardness = fields.Char(string="Required Hardness")
    required_date = fields.Date(string="Required Date")
    partner_id = fields.Many2one('res.partner','Vendor Name', readonly=False)
    stock_delivery_line = fields.One2many('stock.delivery.line', 'delivery_id','BOM Line')

    @api.model
    def default_get(self, fields):
        res = super(StockDelivery, self).default_get(fields)
        res_id = self._context.get('active_id')
        progress = self.env['job.progress'].browse(res_id)
        if progress.raw_uom_qty == (progress.delivery_uom_qty + self.progress_id.prd_in_uom_qty + self.progress_id.prd_out_uom_qty):
            raise ValidationError(_("Already Delivared all the Raw Materials"))
        return res


    @api.depends('progress_id')
    def _compute_raw_uom_qty(self):
        for wizard in self:
            wizard.raw_uom_qty = wizard.progress_id.raw_uom_qty

    @api.depends('progress_id')
    def _compute_flow_type(self):
        for wizard in self:
            wizard.flow_type = wizard.progress_id.flow_type

    @api.depends('progress_id')
    def _compute_flow_code(self):
        for wizard in self:
            wizard.flow_code = wizard.progress_id.flow_id.code

    def generate_product(self):
        for del_id in self.env['stock.raw.line'].search([('delivery_id','=',self.id)]):
            del_id.unlink()
        bom = self.env['job.bom.line'].search([('bom_id','=',self.progress_id.job_id.id)])
        for data in bom:
            val = {
            'delivery_id':self.id,
            'product_id':data.product_id.id,
            'product_qty':data.required_qty - (self.progress_id.delivery_uom_qty + self.progress_id.prd_in_uom_qty + self.progress_id.prd_out_uom_qty),
            'product_uom_id':data.product_uom_id.id,
            }
            self.env['stock.raw.line'].create(val)
        return {
            'name': 'Delivery',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock.delivery',
            'res_id': self.id,
            'nodestroy': True,
            'target': 'new',
        }

    def create_dc(self):
        if not self.job_raw_line:
            raise ValidationError(_("You Cant't Create without Quantity Line Item"))
        recent_qty = 0.0
        for line in self.job_raw_line:
            recent_qty += line.product_qty
        if self.progress_id.raw_uom_qty < self.progress_id.delivery_uom_qty + self.progress_id.prd_in_uom_qty + self.progress_id.prd_out_uom_qty + recent_qty:
            raise ValidationError(_("You Cant't Create DC More Then Required Quantity"))
        state = 'production' if self.mrp_type == 'internal' else 'Done'
        sequance = self.env['ir.sequence'].next_by_code('job.production') if self.mrp_type == 'internal' else self.env['ir.sequence'].next_by_code('job.outward')
        val = {
        'name':sequance or _("New"),
        'state':state,
        'type':'outward',
        'dc_date':self.dc_date,
        'flow_type':self.progress_id.flow_type,
        'job_id':self.progress_id.job_id.id,
        'sale_id':self.progress_id.sale_id.id,
        'flow_id':self.progress_id.flow_id.id,
        'jh_no':self.progress_id.jh_no,
        'partner_id':self.partner_id.id,
        'mrp_type':self.mrp_type,
        'progress_id':self.progress_id.id,
        'ht_type':self.ht_type,
        'required_hardness':self.required_hardness,
        'required_date':self.required_date,
        'flow_code':self.flow_code,
        }
        out = self.env['job.inward'].create(val)
        current_qty = 0.0
        for line in self.job_raw_line:
            val_line = {
            'inward_id':out.id,
            'product_id':line.product_id.id,
            'product_qty':line.product_qty,
            'product_uom_id':line.product_uom_id.id,
            }
            self.env['job.inward.line'].create(val_line)
            current_qty += line.product_qty

        picking_type = self.env['stock.picking.type'].search([('code','=','internal'), ('sequence_code','=','INT')], limit=1)
        location = self.env['stock.location'].search([('usage','=','internal')], limit=1)
        location_dest = self.env['stock.location'].search([('usage','=','production')], limit=1)
        picking_data = {
        'picking_type_id':picking_type.id,
        'location_id':location.id,
        'location_dest_id':location_dest.id,
        'job_id':self.progress_id.job_id.id,
        'origin':'Auto Transfer Qty Job',
        }
        picking = self.env['stock.picking'].create(picking_data)
        for line in self.job_raw_line:
            move_data = {
            'product_id':line.product_id.id,
            'name':line.product_id.name,
            'product_uom':line.product_uom_id.id,
            'location_id':location.id,
            'location_dest_id':location_dest.id,
            'picking_id':picking.id,
            'picking_type_id':picking_type.id,
            'product_uom_qty':line.product_qty,
            'quantity':line.product_qty,

            }
            self.env['stock.move'].create(move_data)
        picking.button_validate()
        return True

    #Except Cutting
    def gen_prod(self):
        for del_id in self.env['stock.delivery.line'].search([('delivery_id','=',self.id)]):
            del_id.unlink()
        cycle = self.env['flow.cycle.line'].search([('bom_id','=',self.progress_id.job_id.id),('flow_end_id','=',self.progress_id.flow_id.id)], limit=1)
        inward = self.env['job.inward'].search([('job_id','=',self.progress_id.job_id.id),('flow_id','=',cycle.flow_start_id.id),('type','=','inward'),('quality_type','=','good')])
        for inv in inward:
            for line in inv.job_inward_line:
                if line.received_qty != line.product_qty:
                    vals = {
                    'delivery_id':self.id,
                    'product_id':line.product_id.id,
                    'outward_id':inv.id,
                    'mrp_type':inv.mrp_type,
                    'actual_qty':line.product_qty,
                    'received_qty':line.received_qty,
                    'product_uom_id':line.product_uom_id.id,
                    }
                    self.env['stock.delivery.line'].create(vals)

        return {
            'name': 'Delivery',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock.delivery',
            'res_id': self.id,
            'nodestroy': True,
            'target': 'new',
        }
    def create_delivery(self):
        if not self.stock_delivery_line:
            raise ValidationError(_("You Cant't Create without Quantity Line Item"))
        final_qty = 0.0
        cycle = self.env['flow.cycle.line'].search([('bom_id','=',self.progress_id.job_id.id),('flow_end_id','=',self.progress_id.flow_id.id)], limit=1)
        for line in self.stock_delivery_line:
            if line.product_qty != 0.0:
                if line.product_qty + line.received_qty > line.actual_qty:
                    raise ValidationError(_("You cant't Deliver more then Actual Quantity"))
                final_qty += line.product_qty
        state = 'production' if self.mrp_type == 'internal' else 'Done'
        sequance = self.env['ir.sequence'].next_by_code('job.production') if self.mrp_type == 'internal' else self.env['ir.sequence'].next_by_code('job.outward')
        val = {
        'name':sequance or _("New"),
        'state':state,
        'type':'outward',
        'dc_date':self.dc_date,
        'flow_type':self.progress_id.flow_type,
        'job_id':self.progress_id.job_id.id,
        'sale_id':self.progress_id.sale_id.id,
        'flow_id':self.progress_id.flow_id.id,
        'jh_no':self.progress_id.jh_no,
        'partner_id':self.partner_id.id,
        'mrp_type':self.mrp_type,
        'progress_id':self.progress_id.id,
        'ht_type':self.ht_type,
        'required_hardness':self.required_hardness,
        'required_date':self.required_date,
        'flow_code':self.flow_code,
        }
        inv_obj = self.env['job.inward'].create(val)
        val_line = {
        'inward_id':inv_obj.id,
        'product_id':cycle.flow_start_id.product_id.id,
        'product_qty':final_qty,
        'product_uom_id':1,
        }
        self.env['job.inward.line'].create(val_line)
        for out in self.stock_delivery_line:
            for line in out.outward_id.job_inward_line:
                line.write({'received_qty':line.received_qty + out.product_qty})
        return True



class StockRawLine(models.TransientModel):
    _name = 'stock.raw.line'
    _description = "Stock Raw Line"

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    delivery_id = fields.Many2one('stock.delivery', 'Delivery')
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null',domain="[('purchase_ok', '=', True)]")
    product_qty = fields.Float('Quantity', default=1.0, digits='Percentage Analytic', required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Uom', default=_get_default_product_uom_id,required=True)


class StockDeliveryLine(models.TransientModel):
    _name = 'stock.delivery.line'
    _description = "Stock Raw Line"

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    delivery_id = fields.Many2one('stock.delivery', 'Delivery')
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null',domain="[('purchase_ok', '=', True)]")
    outward_id = fields.Many2one('job.inward', 'Bundle Number')
    mrp_type = fields.Selection(MRP_STATUS, string="Contract Type", required=True)
    actual_qty = fields.Float('Actual Qty', default=0.0, digits='Product Unit of Measure', required=True)
    received_qty = fields.Float('Received Qty', default=0.0, digits='Product Unit of Measure', required=True)
    product_qty = fields.Float('Quantity', default=0.0, digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Uom', default=_get_default_product_uom_id,required=True)


class StockReceipt(models.TransientModel):
    _name = 'stock.receipt'
    _inherit = 'mail.composer.mixin'
    _description = "Stock Receipt"

    name = fields.Char("Name")
    progress_id = fields.Many2one('job.progress', default=lambda self: self.env.context.get('active_id'))
    flow_type = fields.Selection(JOB_STATUS, string="Flow Status", compute='_compute_flow_type', store=True)
    quality_type = fields.Selection(QC_STATUS, string="Quality Type", required=True)
    receipt_no = fields.Char('Receipt Number', required=True)
    receipt_date = fields.Date('Receipt Date', required=True)
    flow_code = fields.Char(string="Flow Code", compute='_compute_flow_code')
    ht_report_number = fields.Char(string="HT Report No")
    micro_report_number = fields.Char(string="Micro Report No")
    stock_receipt_line = fields.One2many('stock.receipt.line', 'receipt_id','BOM Line')

    @api.model
    def default_get(self, fields):
        res = super(StockReceipt, self).default_get(fields)
        res_id = self._context.get('active_id')
        progress = self.env['job.progress'].browse(res_id)
        if progress.received_uom_qty + progress.scrap_uom_qty == progress.product_uom_qty:
            raise ValidationError(_("You cant't do this operation"))
        return res

    @api.depends('progress_id')
    def _compute_flow_code(self):
        for wizard in self:
            wizard.flow_code = wizard.progress_id.flow_id.code

    @api.depends('progress_id')
    def _compute_flow_type(self):
        for wizard in self:
            wizard.flow_type = wizard.progress_id.flow_type

    def generate_product(self):
        for del_id in self.env['stock.receipt.line'].search([('receipt_id','=',self.id)]):
            del_id.unlink()

        data = self.env['job.inward'].search([('progress_id','=',self.progress_id.id),('type','=','outward'),('state','=','Done')])
        for out in data:
            for line in out.job_inward_line:
                if round(line.product_qty / self.progress_id.cutting_size) != round(line.received_qty):
                    val = {
                    'outward_id':out.id,
                    'product_id':self.progress_id.flow_id.product_id.id,
                    'actual_qty':line.product_qty / self.progress_id.cutting_size,
                    'received_qty':line.received_qty,
                    'product_uom_id':self.progress_id.flow_id.product_id.uom_id.id,
                    'receipt_id':self.id,
                    'mrp_type':out.mrp_type,
                    }
                    self.env['stock.receipt.line'].create(val)

        return {
            'name': 'Receipt',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock.receipt',
            'res_id': self.id,
            'nodestroy': True,
            'target': 'new',
        }

    def create_receipt(self):
        if not self.stock_receipt_line:
            raise ValidationError(_("You Cant't Create without Quantity Line Item"))
        for line in self.stock_receipt_line:
            if line.product_qty != 0.0:
                if line.product_qty + line.received_qty > line.actual_qty:
                    raise ValidationError(_("You cant't Receive Qty more then Actual"))
        total_qty = 0.0
        for line in self.stock_receipt_line:
            if line.product_qty != 0.0:
                total_qty += line.product_qty
        sequance = self.env['ir.sequence'].next_by_code('job.inward') if self.quality_type == 'good' else self.env['ir.sequence'].next_by_code('job.scrap')
        val = {
        'name':sequance,
        'state':'Done',
        'type':'inward',
        'dc_date':self.receipt_date,
        'flow_type':self.progress_id.flow_type,
        'job_id':self.progress_id.job_id.id,
        'sale_id':self.progress_id.sale_id.id,
        'flow_id':self.progress_id.flow_id.id,
        'jh_no':self.progress_id.jh_no,
        'progress_id':self.progress_id.id,
        'receipt_no':self.receipt_no,
        'quality_type':self.quality_type,
        'mrp_type':'external',
        'flow_code':self.flow_code,
        'ht_report_number':self.ht_report_number,
        'micro_report_number':self.micro_report_number,
        }
        receipt = self.env['job.inward'].create(val)
        val_line = {
        'inward_id':receipt.id,
        'product_id':self.progress_id.flow_id.product_id.id,
        'product_qty':total_qty,
        }
        self.env['job.inward.line'].create(val_line)
        for out in self.stock_receipt_line:
            for line in out.outward_id.job_inward_line:
                line.write({'received_qty':line.received_qty + out.product_qty})
        return True

    def gen_prod(self):
        for del_id in self.env['stock.receipt.line'].search([('receipt_id','=',self.id)]):
            del_id.unlink()

        data = self.env['job.inward'].search([('progress_id','=',self.progress_id.id),('type','=','outward'),('state','=','Done')])
        for out in data:
            for line in out.job_inward_line:
                if line.product_qty != line.received_qty:
                    val = {
                    'outward_id':out.id,
                    'product_id':self.progress_id.flow_id.product_id.id,
                    'actual_qty':line.product_qty,
                    'received_qty':line.received_qty,
                    'product_uom_id':self.progress_id.flow_id.product_id.uom_id.id,
                    'receipt_id':self.id,
                    'mrp_type':out.mrp_type,
                    }
                    self.env['stock.receipt.line'].create(val)
        return {
            'name': 'Receipt',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock.receipt',
            'res_id': self.id,
            'nodestroy': True,
            'target': 'new',
        }

    def receive_final_goods(self,product_qty):
        picking_type = self.env['stock.picking.type'].search([('code','=','incoming'), ('sequence_code','=','IN')], limit=1)
        location = self.env['stock.location'].search([('usage','=','supplier')], limit=1)
        location_dest = self.env['stock.location'].search([('usage','=','internal')], limit=1)
        picking_data = {
        'picking_type_id':picking_type.id,
        'location_id':location.id,
        'location_dest_id':location_dest.id,
        'job_id':self.progress_id.job_id.id,
        'origin':'Auto Received Qty Job',
        }
        picking = self.env['stock.picking'].create(picking_data)
        move_data = {
        'product_id':self.progress_id.product_id.id,
        'name':self.progress_id.product_id.name,
        'product_uom':1,
        'location_id':location.id,
        'location_dest_id':location_dest.id,
        'picking_id':picking.id,
        'picking_type_id':picking_type.id,
        'product_uom_qty':product_qty,
        'quantity':product_qty,

        }
        self.env['stock.move'].create(move_data)
        picking.button_validate()

    def create_receiver(self):
        if not self.stock_receipt_line:
            raise ValidationError(_("You Cant't Create without Quantity Line Item"))
        for line in self.stock_receipt_line:
            if line.product_qty != 0.0:
                if line.product_qty + line.received_qty > line.actual_qty:
                    raise ValidationError(_("You cant't Receive Qty more then Actual"))
        total_qty = 0.0
        for line in self.stock_receipt_line:
            if line.product_qty != 0.0:
                total_qty += line.product_qty
        sequance = self.env['ir.sequence'].next_by_code('job.inward') if self.quality_type == 'good' else self.env['ir.sequence'].next_by_code('job.scrap')
        val = {
        'name':sequance or _("New"),
        'state':'Done',
        'type':'inward',
        'dc_date':self.receipt_date,
        'flow_type':self.progress_id.flow_type,
        'job_id':self.progress_id.job_id.id,
        'sale_id':self.progress_id.sale_id.id,
        'flow_id':self.progress_id.flow_id.id,
        'jh_no':self.progress_id.jh_no,
        'progress_id':self.progress_id.id,
        'receipt_no':self.receipt_no,
        'quality_type':self.quality_type,
        'mrp_type':'external',
        'flow_code':self.flow_code,
        'ht_report_number':self.ht_report_number,
        'micro_report_number':self.micro_report_number,
        }
        receipt = self.env['job.inward'].create(val)
        val_line = {
        'inward_id':receipt.id,
        'product_id':self.progress_id.flow_id.product_id.id,
        'product_qty':total_qty,
        }
        self.env['job.inward.line'].create(val_line)
        for out in self.stock_receipt_line:
            for line in out.outward_id.job_inward_line:
                line.write({'received_qty':line.received_qty + out.product_qty})
        if self.flow_type == 'fg' and self.quality_type == 'good':
            self.receive_final_goods(total_qty)

class StockReceiptLine(models.TransientModel):
    _name = 'stock.receipt.line'
    _inherit = 'mail.composer.mixin'
    _description = "Stock Receipt"

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    receipt_id = fields.Many2one('stock.receipt', 'Receipt')
    outward_id = fields.Many2one('job.inward', 'Bundle Number')
    mrp_type = fields.Selection(MRP_STATUS, string="Contract Type", required=True)
    product_id = fields.Many2one(comodel_name='product.product',string="Product",change_default=True, ondelete='restrict', index='btree_not_null')
    actual_qty = fields.Float('Actual Qty', default=1.0, digits='Product Unit of Measure', required=True)
    received_qty = fields.Float('Received Qty', default=1.0, digits='Product Unit of Measure', required=True)
    product_qty = fields.Float('Quantity', default=0.0, digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one('uom.uom', 'Uom', default=_get_default_product_uom_id,required=True)



