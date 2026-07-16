from odoo import http
from odoo.http import request
import xlsxwriter
from io import BytesIO
from datetime import datetime

class PartnerLedgerController(http.Controller):
    @http.route('/web/partner_ledger_report', type="http", auth="user", website=True, csrf=False)
    def partner_ledger_report(self, report_type, start_date, end_date, display_type, partner_id=None, **kwargs):
        data = self._get_data(report_type, start_date, end_date, partner_id)
        open_query = """
            select COALESCE(SUM(aml.debit), 0) as opening_debit, COALESCE(SUM(aml.credit), 0) as opening_credit, COALESCE(SUM(aml.debit - aml.credit), 0) as opening_balance
            FROM account_move_line aml
            JOIN account_account aa ON aml.account_id = aa.id
            WHERE aml.date < %s AND aml.parent_state = 'posted' AND aa.account_type in ('liability_payable', 'asset_receivable') 
            AND aml.partner_id=%s AND aml.company_id = %s
        """
        params = [start_date, partner_id, request.env.company.id]

        request.env.cr.execute(open_query, tuple(params))
        open_balances = request.env.cr.dictfetchall()
        open_debit = open_balances[0]['opening_debit']
        open_credit = open_balances[0]['opening_credit']
        open_bal = open_balances[0]['opening_balance']

        rp_obj = request.env['res.partner'].search([('id', '=', partner_id)])
        if rp_obj:
            partner_name = rp_obj.name

        disp_start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%d-%m-%Y')
        disp_end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%d-%m-%Y')

        if display_type == 'htm':
            if report_type == 'ledger':
                return request.render('sb_partner_ledger.partner_ledger_report_template', {
                    'data': data,
                    'open_debit': open_debit,
                    'open_credit': open_credit,
                    'open_bal': open_bal,
                    'report_type': report_type,
                    'partner_id': partner_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'disp_start_date': disp_start_date,
                    'disp_end_date': disp_end_date,
                    'partner_name': partner_name,
                    'company_name': request.env.user.company_id.name
                })
            else:
                return request.render('sb_partner_ledger.partner_ledger_report_detail_template', {
                    'data': data,
                    'open_debit': open_debit,
                    'open_credit': open_credit,
                    'open_bal': open_bal,
                    'report_type': report_type,
                    'partner_id': partner_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'disp_start_date': disp_start_date,
                    'disp_end_date': disp_end_date,
                    'partner_name': partner_name,
                    'company_name': request.env.user.company_id.name
                })
        elif display_type == 'xls':
            if report_type == 'ledger':
                file_content = self._create_excel_ledger_file(partner_name, data, open_debit, open_credit, open_bal, start_date, end_date)
                file_name = f"partner_ledger_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
            else:
                file_content = self._create_excel_detail_file(partner_name, data, open_debit, open_credit, open_bal, start_date, end_date)
                file_name = f"partner_ledger_report_item_wise_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"

            return request.make_response(
                file_content,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', f'attachment; filename={file_name}')
                ]
            )
        else:
            datas = {
                'det_data': data, 'partner_name': partner_name, 'open_debit': open_debit, 'open_credit': open_credit,
                 'open_bal': open_bal, 'start_date': disp_start_date, 'end_date': disp_end_date, 'company_name': request.env.user.company_id.name
            }
            if report_type == 'ledger':
                pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf('sb_partner_ledger.action_partner_ledger_report',  data=datas)[0]
            else:
                pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf('sb_partner_ledger.action_partner_ledger_report_detail',  data=datas)[0]

            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf)),
            ]
            return request.make_response(pdf, headers=pdfhttpheaders)

    def _get_data(self, report_type, start_date, end_date, partner_id=None):
        if report_type == 'ledger':
            return self._get_partner_ledger_data(start_date, end_date, partner_id)
        else:
            return self._get_partner_detail_data(start_date, end_date, partner_id)

    def _get_partner_ledger_data(self, start_date, end_date, partner_id=None):
        company_id = request.env.company.id
        query = """
            select aml.date, TO_CHAR(aml.date, 'DD-MM-YYYY') as invdate, aml.move_name as vchno, aml.ref as narration, aml.debit, aml.credit
            FROM account_move_line aml
            JOIN account_account aa ON aml.account_id = aa.id
            WHERE aml.date BETWEEN %s AND %s AND aml.partner_id=%s AND aml.company_id = %s AND aml.parent_state = 'posted' 
            AND aa.account_type in ('liability_payable', 'asset_receivable')
            order by aml.date, aml.id
         """
        params = [start_date, end_date, partner_id, company_id]

        request.env.cr.execute(query, tuple(params))
        result = request.env.cr.dictfetchall()

        report_data = []
        for line in result:
                report_data.append({
                    'invdate':line['invdate'],
                    'vchno': line['vchno'],
                    'narration': line['narration'],
                    'debit': line['debit'],
                    'credit': line['credit']
                })
        return report_data

    def _get_partner_detail_data(self, start_date, end_date, partner_id=None):
        company_id = request.env.company.id
        query = """
            select aml.id, aml.date, TO_CHAR(aml.date, 'DD-MM-YYYY') as invdate, aml.move_name as vchno, aml.ref as narration, aml.debit, aml.credit, '' as product_name, 0 as quantity, 0 as price_unit
            FROM account_move_line aml
            JOIN account_account aa ON aml.account_id = aa.id
            WHERE aml.date BETWEEN %s AND %s AND aml.partner_id=%s AND aml.company_id = %s AND aml.parent_state = 'posted' 
            AND aa.account_type in ('liability_payable', 'asset_receivable')
            union all
            select aml.id, aml.date, TO_CHAR(aml.date, 'DD-MM-YYYY') as invdate, aml.move_name as vchno, aml.name as narration, 0 as debit, 
            0 as credit, 'abc' as product_name, aml.quantity, aml.price_unit
            FROM account_move_line aml
            JOIN account_account aa ON aml.account_id = aa.id
            WHERE aml.date BETWEEN %s AND %s AND aml.partner_id=%s AND aml.company_id = %s AND aml.parent_state = 'posted' 
            AND aa.account_type in ('income', 'asset_current')
            order by date,id desc
            """
        params = [start_date, end_date, partner_id, company_id, start_date, end_date, partner_id, company_id]

        request.env.cr.execute(query, tuple(params))
        result = request.env.cr.dictfetchall()

        report_data = []
        for line in result:
                report_data.append({
                    'invdate': line['invdate'],
                    'vchno': line['vchno'],
                    'narration': line['narration'],
                    'debit': line['debit'],
                    'credit': line['credit'],
                    'product_name': line['product_name'],
                    'quantity': line['quantity'],
                    'price_unit': line['price_unit']
                })
        return report_data

    def _create_excel_ledger_file(self, partner_name, data, open_debit, open_credit, open_bal, start_date, end_date):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Partner Ledger Report')

        decimal_format = workbook.add_format({'num_format': '#,##0.00'})
        bold = workbook.add_format({'bold': True})
        format0 = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })
        format1 = workbook.add_format({
            'bold': True,
            'top': 1,
            'num_format': '#,##0.00'
        })
        format2 = workbook.add_format({
            'bold': True,
            'align': 'center',
            'border': 1
        })
        format3 = workbook.add_format({
            'bold': True,
            'align': 'center',
            'top': 1,
        })

        c = 0
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 20)
        c += 1
        worksheet.set_column(c, c, 50)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)

        # Get the company name
        company_name = request.env.user.company_id.name

        row = 0
        # Write the company name to the first row
        worksheet.merge_range(row, 0, row, 5, company_name, format0)

        row = row + 1
        worksheet.merge_range(row, 0, row, 5, 'Partner Ledger Report', format0)
        headers = ['Dated', 'Voucher No', 'Narration', 'Debit', 'Credit', 'Balance']


        row = row + 1
        start_date_str = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_str = datetime.strptime(end_date, "%Y-%m-%d")
        worksheet.write(row, 0, "Date From: "+start_date_str.strftime('%d-%m-%Y'), bold)
        worksheet.write(row, 4, "Date To: "+end_date_str.strftime('%d-%m-%Y'), bold)

        row = row + 1
        worksheet.write(row, 0, "Account Title: "+partner_name, bold)

        # Write the header starting from the second row
        row = row + 1
        for col_num, header in enumerate(headers):
            worksheet.write(row, col_num, header, format2)

        # Write the data
        run_balance = 0
        row = row + 1

        worksheet.write(row, 0, '')
        worksheet.write(row, 1, '')
        worksheet.write(row, 2, 'Opening Balance')
        worksheet.write(row, 3, open_debit, decimal_format)
        worksheet.write(row, 4, open_credit, decimal_format)
        worksheet.write(row, 5, open_bal, decimal_format)
        run_balance = run_balance + open_bal

        row = row + 1
        for row_num, line in enumerate(data, start=row):
            run_balance = run_balance + line['debit'] - line['credit']
            worksheet.write(row_num, 0, line['invdate'])
            worksheet.write(row_num, 1, line['vchno'])
            worksheet.write(row_num, 2, line['narration'])
            worksheet.write(row_num, 3, line['debit'], decimal_format)
            worksheet.write(row_num, 4, line['credit'], decimal_format)
            worksheet.write(row_num, 5, run_balance, decimal_format)

        row_num = row_num + 1
        for col in range(ord('A') - ord('A'), ord('F') - ord('A') + 1):
            worksheet.write(row_num, col, '', format1)

        worksheet.write(row_num, 2, 'Grand Total', format3)
        for col in range(3, 5):  # Columns D to E (3 to 5)
            col_letter = chr(65 + col)  # Convert column number to letter (D to E)
            sum_formula = f'=SUM({col_letter}6:{col_letter}{row_num})'
            worksheet.write(row_num, col, sum_formula, format1)
            worksheet.write(row_num, 5, run_balance, format1)

        workbook.close()
        output.seek(0)
        return output.read()

    def _create_excel_detail_file(self, partner_name, data, open_debit, open_credit, open_bal, start_date, end_date):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Partner Ledger Report Item Wise')

        decimal_format = workbook.add_format({
            'num_format': '#,##0.00',
            'valign': 'vcenter'
        })
        decimal_format_qty = workbook.add_format({
            'num_format': '#,##0.000',
            'valign': 'vcenter'
        })
        bold = workbook.add_format({'bold': True})
        wrap_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'vcenter'
        })
        wrap_center = workbook.add_format({
            'text_wrap': True,
            'align': 'center',
            'valign': 'vcenter'
        })
        format0 = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })
        format1 = workbook.add_format({
            'bold': True,
            'top': 1,
            'num_format': '#,##0.00'
        })
        format2 = workbook.add_format({
            'bold': True,
            'align': 'center',
            'border': 1
        })
        format3 = workbook.add_format({
            'bold': True,
            'align': 'center',
            'top': 1,
        })

        c = 0
        worksheet.set_column(c, c, 12)
        c += 1
        worksheet.set_column(c, c, 20)
        c += 1
        worksheet.set_column(c, c, 50)
        c += 1
        worksheet.set_column(c, c, 10)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)

        # Get the company name
        company_name = request.env.user.company_id.name

        row = 0
        # Write the company name to the first row
        worksheet.merge_range(row, 0, row, 7, company_name, format0)

        row = row + 1
        worksheet.merge_range(row, 0, row, 7, 'Partner Ledger Detail Report', format0)
        headers = ['Dated', 'Voucher No', 'Narration', 'Qty', 'Rate', 'Debit', 'Credit', 'Balance']

        row = row + 1
        start_date_str = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_str = datetime.strptime(end_date, "%Y-%m-%d")
        worksheet.write(row, 0, "Date From: "+start_date_str.strftime('%d-%m-%Y'), bold)
        worksheet.write(row, 6, "Date To: "+end_date_str.strftime('%d-%m-%Y'), bold)

        row = row + 1
        worksheet.write(row, 0, "Account Title: "+partner_name, bold)

        # Write the header starting from the second row
        row = row + 1
        for col_num, header in enumerate(headers):
            worksheet.write(row, col_num, header, format2)

        # Write the data
        run_balance = 0
        row = row + 1

        worksheet.write(row, 0, '')
        worksheet.write(row, 1, '')
        worksheet.write(row, 2, 'Opening Balance')
        worksheet.write(row, 3, '')
        worksheet.write(row, 4, '')
        worksheet.write(row, 5, open_debit, decimal_format)
        worksheet.write(row, 6, open_credit, decimal_format)
        worksheet.write(row, 7, open_bal, decimal_format)
        run_balance = run_balance + open_bal

        row = row + 1
        for row_num, line in enumerate(data, start=row):
            run_balance = run_balance + line['debit'] - line['credit']

            worksheet.write(row_num, 0, line['invdate'], wrap_center)
            worksheet.write(row_num, 1, line['vchno'], wrap_format)
            worksheet.write(row_num, 2, line['narration'], wrap_format)
            if line['product_name']:
                worksheet.write(row_num, 3, line['quantity'], decimal_format_qty)
                worksheet.write(row_num, 4, line['price_unit'], decimal_format)
                worksheet.write(row_num, 5, '')
                worksheet.write(row_num, 6, '')
            else:
                worksheet.write(row_num, 3, '')
                worksheet.write(row_num, 4, '')
                worksheet.write(row_num, 5, line['debit'], decimal_format)
                worksheet.write(row_num, 6, line['credit'], decimal_format)
            worksheet.write(row_num, 7, run_balance, decimal_format)

        row_num = row_num + 1
        for col in range(ord('A') - ord('A'), ord('H') - ord('A') + 1):
            worksheet.write(row_num, col, '', format1)

        worksheet.write(row_num, 3, 'Grand Total', format3)
        for col in range(5, 7):  # Columns F to G (5 to 7)
            col_letter = chr(65 + col)  # Convert column number to letter (F to G)
            sum_formula = f'=SUM({col_letter}6:{col_letter}{row_num})'
            worksheet.write(row_num, col, sum_formula, format1)
            worksheet.write(row_num, 7, run_balance, format1)

        workbook.close()
        output.seek(0)
        return output.read()
