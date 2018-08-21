# -*- coding: utf-8 -*-
# Copyright 2012-2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, models


class ShellAccount(object):

    # Small class that avoid to override account account object
    # only for pure perfomance reason.
    # Browsing an account account object is not efficient
    # beacause of function fields
    # This object aim to be easly transpose to account account if needed

    def __init__(self, account):
        self.cursor = account.env.cr
        tmp = account.read(
            ['id', 'name', 'code', 'currency_revaluation'])
        self.account_id = tmp[0]['id']
        self.ordered_lines = []
        self.keys_to_sum = ['gl_foreign_balance', 'gl_currency_rate',
                            'gl_revaluated_balance', 'gl_balance',
                            'gl_ytd_balance']

    def __contains__(self, key):
        return hasattr(self, key)

    def get_lines(self):
        """Get all line account move line that are need on report for current
        account.
        """
        sql = """SELECT 
                    res_partner.name,
                    account_move_line.date,
                    coalesce(account_move_line.gl_foreign_balance, 0),
                    coalesce(account_move_line.gl_currency_rate, 0),
                    coalesce(account_move_line.gl_revaluated_balance, 0),
                    coalesce(account_move_line.gl_balance, 0),
                    coalesce(account_move_line.gl_revaluated_balance, 0) -
                    coalesce(account_move_line.gl_balance, 0) as gl_ytd_balance,
                    res_currency.name as curr_name
                 FROM account_move_line
                   LEFT join res_partner on
                     (account_move_line.partner_id = res_partner.id)
                   LEFT join account_move on
                     (account_move_line.move_id = account_move.id)
                   LEFT join res_currency on
                     (account_move_line.currency_id = res_currency.id)
                 WHERE account_move_line.account_id = %s
                 ORDER BY res_partner.name,
                   account_move_line.gl_foreign_balance,
                   account_move_line.date"""
        self.cursor.execute(sql, [self.account_id])
        self.ordered_lines = self.cursor.dictfetchall()
        return self.ordered_lines

    def compute_totals(self):
        """Compute the sum of values in self.ordered_lines"""
        totals = dict.fromkeys(self.keys_to_sum, 0.0)
        for line in self.ordered_lines:
            for tot in self.keys_to_sum:
                totals[tot] += line.get(tot, 0.0)
        for key, val in totals.iteritems():
            setattr(self, key + '_total', val)


class CurrencyUnrealizedReport(models.AbstractModel):
    _name = 'report.account_multicurrency_revaluation.curr_unrealized'

    @api.model
    def render_html(self, docids, data=None):
        shell_accounts = {}
        docs = self.env['account.account']
        data = data if data is not None else {}
        accounts = self.env['account.account'].search(
            [('currency_revaluation', '=', True)])
        for account in accounts:
            acc = ShellAccount(account)
            acc.get_lines()
            if acc.ordered_lines:
                docs |= account
                shell_accounts[account.id] = acc
                acc.compute_totals()
        docargs = {
            'doc_ids': docs.ids,
            'doc_model': 'account.account',
            'docs': docs,
            'shell_accounts': shell_accounts,
            'data': dict(
                data,
            ),
        }
        return self.env['report'].render(self._name[7:], docargs)
