from datetime import date, datetime

from odoo.exceptions import ValidationError
from odoo import models, fields, api

def get_first_july():
    current_date = datetime.now().date()
    year = current_date.year
    if current_date.month > 6:
        return date(year, 7, 1)
    else:
        return date(year - 1, 7, 1)

class PartnerLedgerWizard(models.TransientModel):
    _name = 'partner.ledger.wizard'
    _description = 'Partner Ledger Wizard'

    report_type = fields.Selection([
        ('ledger', 'Ledger'),
        ('detail', 'Detail')
    ], string='Report Type', required=True, default='ledger')
    start_date = fields.Date(string='Start Date', required=True, default=get_first_july())
    end_date = fields.Date(string='End Date', required=True, default=fields.Date.context_today)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.end_date < record.start_date:
                raise ValidationError('End Date must be greater than Start Date.')
            if (record.end_date - record.start_date).days > 365:
                raise ValidationError('The duration between Start Date and End Date should not exceed one year.')

    def generate_report_htm(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        report_url = f"{base_url}/web/partner_ledger_report?report_type={self.report_type}&start_date={self.start_date}&end_date={self.end_date}&partner_id={self.partner_id.id}&display_type=htm"

        # report_url += f"&partner_id={self.partner_id.id}"

        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new'
        }

