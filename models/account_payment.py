from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

# Account Journal
class AccountJournal(models.Model):
    _inherit = 'account.journal'

    show_transaction_id = fields.Boolean(string="Show Transaction ID")


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    transaction_id = fields.Char(string="Transaction ID")


# Account Payment Register
class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    show_transaction_id = fields.Boolean(related='journal_id.show_transaction_id', string="Show Transaction ID", store=True)
    transaction_id = fields.Char(string="Transaction ID", store=True)

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
        payment_vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard()
        if self.transaction_id:
            payment_vals['transaction_id'] = self.transaction_id
        payment_vals['amount'] = self.amount
        return payment_vals

# Account Move
class AccountMove(models.Model):
    _inherit = 'account.move'

    transaction_id = fields.Char(string='Transaction ID')
    
# Sale Order
class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
   
















