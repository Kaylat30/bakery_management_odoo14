from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# Account Journal
class AccountJournal(models.Model):
    _inherit = 'account.journal'

    show_transaction_id = fields.Boolean(string="Show Transaction ID", compute='_compute_show_transaction_id', store=True)

    @api.depends('name')
    def _compute_show_transaction_id(self):
        for record in self:
            record.show_transaction_id = record.name in ['Momo Pay', 'Airtel Pay']

# Account Payment
class AccountPayment(models.Model):
    _inherit = 'account.payment'

    transaction_id = fields.Char(string="Transaction ID", store=True)

# Account Payment Register
class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    transaction_id = fields.Char(string="Transaction ID")
    show_transaction_id = fields.Boolean(compute='_compute_show_transaction_id')

    @api.depends('journal_id')
    def _compute_show_transaction_id(self):
        for record in self:
            record.show_transaction_id = record.journal_id.show_transaction_id if record.journal_id else False

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id and self.journal_id.show_transaction_id:
            self.transaction_id = ''
        else:
            self.transaction_id = False

    @api.constrains('transaction_id')
    def _check_transaction_id_required(self):
        for record in self:
            if record.show_transaction_id and not record.transaction_id:
                raise ValidationError("Transaction ID is required for this journal.")

    def _create_payment_vals_from_wizard(self):
        payment_vals = super()._create_payment_vals_from_wizard()
        if self.transaction_id:
            payment_vals['transaction_id'] = self.transaction_id
        return payment_vals

# Account Move (Invoice)
class AccountMove(models.Model):
    _inherit = 'account.move'

    transaction_id = fields.Char(string="Transaction ID", related='payment_id.transaction_id', store=True, readonly=True)
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_compute_amount')
    amount_tax = fields.Monetary(string='Tax', store=True, readonly=True, compute='_compute_amount')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_amount')
    amount_residual = fields.Monetary(string='Residual Amount', store=True, readonly=True, compute='_compute_amount')
    amount_untaxed_signed = fields.Monetary(string='Untaxed Amount Signed', store=True, readonly=True, compute='_compute_amount')
    amount_tax_signed = fields.Monetary(string='Tax Amount Signed', store=True, readonly=True, compute='_compute_amount')
    amount_total_signed = fields.Monetary(string='Total Amount Signed', store=True, readonly=True, compute='_compute_amount')
    amount_residual_signed = fields.Monetary(string='Residual Amount Signed', store=True, readonly=True, compute='_compute_amount')
    
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed')
    ], string='Payment State', default='not_paid', store=True, compute='_compute_payment_state')

    @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.tax_ids', 'line_ids.amount_residual', 'line_ids.payment_id', 'state')
    def _compute_amount(self):
        for invoice in self:
            # Calculate totals
            total_untaxed = sum(line.price_subtotal for line in invoice.invoice_line_ids)
            total_tax = sum(line.price_total - line.price_subtotal for line in invoice.invoice_line_ids)
            
            invoice.amount_untaxed = total_untaxed - total_tax
            invoice.amount_tax = total_tax
            invoice.amount_total = invoice.amount_untaxed + invoice.amount_tax
            
            # Set amount_residual initially to amount_total
            invoice.amount_residual = invoice.amount_total
            
            # Calculate sign based on move_type
            sign = -1 if invoice.move_type in ['in_refund', 'out_refund'] else 1
            
            # Calculate the sum of line residuals
            sum_residuals = sum(
                line.amount_residual 
                for line in invoice.line_ids.filtered(lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
            )
            
            # Update amount_residual only if payments have been made
            if abs(sum_residuals) < abs(invoice.amount_total):
                invoice.amount_residual = sum_residuals
            
            # Set signed amounts
            invoice.amount_residual_signed = sign * abs(invoice.amount_residual)
            invoice.amount_untaxed_signed = sign * invoice.amount_untaxed
            invoice.amount_tax_signed = sign * invoice.amount_tax
            invoice.amount_total_signed = sign * invoice.amount_total


    @api.depends('amount_residual', 'amount_total', 'line_ids.payment_id.state', 'state')
    def _compute_payment_state(self):
        for invoice in self:
            if invoice.state != 'posted':
                invoice.payment_state = 'not_paid'
            elif invoice.amount_residual == 0:                
                invoice.payment_state = 'paid'                
            elif 0 < invoice.amount_residual < invoice.amount_total:
                invoice.payment_state = 'partial'
            elif invoice.line_ids.payment_id.filtered(lambda p: p.state == 'posted'):
                invoice.payment_state = 'in_payment'
            elif invoice.reversal_move_id and invoice.reversal_move_id.state == 'posted':
                invoice.payment_state = 'reversed'
            else:
                invoice.payment_state = 'not_paid'

    @api.onchange('invoice_line_ids', 'invoice_line_ids.tax_ids')
    def onchange_invoice_line_ids(self):
        self._compute_amount()
        self._compute_payment_state()


# Sale Order
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    amount_untaxed = fields.Monetary(compute='_compute_amount', store=True, readonly=True)
    amount_tax = fields.Monetary(compute='_compute_amount', store=True, readonly=True)
    amount_total = fields.Monetary(compute='_compute_amount', store=True, readonly=True)

    @api.depends('order_line.price_total', 'order_line.price_subtotal', 'order_line.price_tax')
    def _compute_amount(self):
        for order in self:
            amount_untaxed = sum(order.order_line.mapped('price_subtotal')) - sum(order.order_line.mapped('price_tax'))
            amount_tax = sum(order.order_line.mapped('price_tax'))
            amount_total = sum(order.order_line.mapped('price_total'))
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_total,
            })

    def action_confirm(self):
            # Call the original method to ensure standard functionality is preserved
            res = super(SaleOrder, self).action_confirm()
            self.send_confirmation_notification()
            for order in self:
                # Check if the order was in quotation state before confirmation
                if order.state == 'sale':
                    # Perform your custom logic here
                    order.message_post(
                        body=f'Sales Order {order.name} has been comfirmed.',
                        message_type='notification',
                        subtype_id=self.env.ref('mail.mt_note').id
                    )
            return res

    def send_confirmation_notification(self):
        for order in self:
            message = f"Sales Order {order.name} has been confirmed."
            channel = self.env['mail.channel'].sudo().search([('name', '=', 'Sales Notifications')], limit=1)
            
            if not channel:
                channel = self.env['mail.channel'].sudo().create({
                    'name': 'Sales Notifications',
                    'channel_type': 'channel',
                    'public': 'public',
                })

            channel.message_post(body=message, message_type='notification', subtype_xmlid='mail.mt_comment')

        return True        
   
# Sale Order Line
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'price_unit', 'product_uom_qty', 'tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(
                price,
                line.order_id.currency_id,
                line.product_uom_qty,
                product=line.product_id,
                partner=line.order_id.partner_shipping_id
            )
            
            
            line.price_total = line.price_unit * line.product_uom_qty
            line.price_tax = sum(t.get('amount', 0.0) for t in taxes['taxes'])
            line.price_subtotal = line.price_total

    @api.depends('price_subtotal', 'price_total')
    def _get_price_reduce(self):
        for line in self:
            line.price_reduce = line.price_total / line.product_uom_qty if line.product_uom_qty else 0.0
            line.price_reduce_taxinc = line.price_total / line.product_uom_qty if line.product_uom_qty else 0.0
            line.price_reduce_taxexcl = line.price_subtotal / line.product_uom_qty if line.product_uom_qty else 0.0

















