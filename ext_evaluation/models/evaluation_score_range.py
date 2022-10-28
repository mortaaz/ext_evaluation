# -*- coding: utf-8 -*-


from cmath import nan
import string

from jmespath import search
from odoo import models, fields, api
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RangeCategoryItems(models.Model):
    _name = "range.category.items"
    _description = "Range Category Items"
    _inherit = ['mail.thread']

    name = fields.Char(string='Range Name', compute='_get_name')
    weight = fields.Float(string="Weight")
    lower_bound = fields.Float(string="Lower Bound")
    upper_bound = fields.Float(string="Upper Bound")
    range_category_id = fields.Many2one('range.category', string="Range Category")
    is_active = fields.Boolean(string="Active")

    @api.one
    @api.depends('weight','lower_bound','upper_bound')
    def _get_name(self):
        self.name = self.weight + ' ' + self.lower_bound + ' ' + self.upper_bound


class RangeCategory(models.Model):
    _name = "range.category"
    _description = "Range Category"
    

    name = fields.Char(string='Range Name', compute='_get_name')
    period_id = fields.Many2one('evaluation.period', string = "Period",required = True)
    is_active = fields.Boolean(string="Active")
    range_category_items_ids = fields.One2many('range.category.items', 'range_category_id', string="Range and Corrosponding Weight", domain = [('is_active','=',True)])

    @api.one
    @api.depends('period_id')
    def _get_name(self):
        self.name = 'Range Category'+ ' ' + self.period_id       


class ScoreRangeCalculation(models.Model):
    _name = 'score.range.calculation'
    _description = "Score Range Calculation"

#   related
    period_id = fields.Many2one(related='range_category_id.period_id', string = "Period", required = True)
    range_category_id = fields.Many2one('range.category', string='Score Range')
    range_category_item_id = fields.Many2one('range.category.items', string="Range Category Item")
    first_line_manager_id = fields.Many2one('hr.employee', string="First Line Manager", required=True,domain=[('state','=','onboard')])   
    average_score = fields.Float(compute = '_average_line_score', readonly=True, string="Average Line Score")

    def _average_line_score(self):
        # first_line_manager_list = self.env['hr.employee'].search([('is_line_manager','=',True)])
        # score_list = []
        self.env.cr.execute("""select count(final_score) from evaluation_evaluation where period_id = {} and first_line_manager_id = {} and final_score >= {} and final_score <= {}"""
                            .format(self.period_id.id,self.first_line_manager_id.id,self.range_category_item_id.lower_bound,self.range_category_item_id.upper_bound,))
        score = self.env.cr.fetchone()
        return score 