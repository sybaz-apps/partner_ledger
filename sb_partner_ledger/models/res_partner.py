from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = "res.partner"

    current_balance = fields.Monetary(string="Current Balance", compute='_compute_current_balance')

    def _compute_current_balance(self):
        for partner in self:
            query = """
                SELECT COALESCE(SUM(aml.debit - aml.credit), 0) as current_balance
                FROM account_move_line aml
                JOIN account_account aa ON aml.account_id = aa.id
                WHERE aml.parent_state = 'posted' AND aa.account_type in ('liability_payable', 'asset_receivable') 
                AND aml.partner_id = %s AND aml.company_id = %s
            """
            self.env.cr.execute(query, (partner.id, self.env.company.id))
            partner.current_balance = self.env.cr.fetchone()[0]
