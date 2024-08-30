from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
import logging

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

    @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.tax_ids')
    def _compute_amount(self):
        for invoice in self:
            total_untaxed = 0.0
            total_tax = 0.0
            for line in invoice.invoice_line_ids:
                price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                taxes = line.tax_ids.compute_all(
                    price_unit,
                    invoice.currency_id,
                    line.quantity,
                    product=line.product_id,
                    partner=invoice.partner_id
                )
                total_untaxed += taxes['total_excluded']
                total_tax += sum(t.get('amount', 0.0) for t in taxes['taxes'])
            invoice.amount_untaxed = total_untaxed - total_tax
            invoice.amount_tax = total_tax
            invoice.amount_total = invoice.amount_untaxed + invoice.amount_tax 

    @api.onchange('invoice_line_ids', 'invoice_line_ids.tax_ids')
    def _onchange_invoice_line_ids(self):
        self._compute_amount()
        
# Sale Order
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line.price_total', 'order_line.price_subtotal', 'order_line.price_tax')
    def _compute_amount(self):
        for order in self:
            order.amount_untaxed = sum(line.price_subtotal for line in order.order_line)
            order.amount_tax = sum(line.price_tax for line in order.order_line)
            order.amount_total = sum(line.price_total for line in order.order_line)

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
            
            line.price_total = price * line.product_uom_qty
            # line.price_total = line.price_unit * line.product_uom_qtyx``
            line.price_tax = sum(t.get('amount', 0.0) for t in taxes['taxes'])
            line.price_subtotal = line.price_total - line.price_tax

    @api.depends('price_subtotal', 'price_total')
    def _get_price_reduce(self):
        for line in self:
            line.price_reduce = line.price_total / line.product_uom_qty if line.product_uom_qty else 0.0
            line.price_reduce_taxinc = line.price_total / line.product_uom_qty if line.product_uom_qty else 0.0
            line.price_reduce_taxexcl = line.price_subtotal / line.product_uom_qty if line.product_uom_qty else 0.0

















