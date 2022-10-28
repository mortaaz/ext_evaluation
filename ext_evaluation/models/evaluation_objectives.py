# -*- coding: utf-8 -*-
# from odoo import api, fields, models, _
from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning




class EvaluationObjectives(models.Model):
    _name = "evaluation.objectives"
    _inherit = ['mail.thread']
    _description = "Evaluation Objectives"
    

    
    # def _default_lm(self):

    #     lm_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)])
    #     if self.user_has_groups('ext_hr_employee.group_line_manager'):
    #         res['fields']['type_of_category_item']['domain'] = [('is_fix', '=', False),('is_active','=',True)]

    #     elif self.user_has_groups('ext_evaluation.group_obj_creator') :

    #         lm_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)]).line_manager
    #     else:
    #         lm_id=''
        
    #     return lm_id



    name = fields.Char(string='Objective Name', required=True , help="Name of evaluation objective."
    ,track_visibility='onchange', readonly=True,states={'new': [('readonly', False)]})
    
    state = fields.Selection([
        ('new', 'New'),         
        ('running', 'Running'), 
        ('closed', 'Closed')],
        string='Status', default='new', readonly=True,track_visibility='onchange', copy=False)
    lm_name = fields.Many2one('hr.employee', string="LM Name",track_visibility='onchange',readonly=True,states={'new': [('readonly', False)]})#, ondelete='cascade'
    type_of_category_item = fields.Many2one('evaluation.category.items', string="Category Item", 
    required=True,track_visibility='onchange', readonly=True,states={'new': [('readonly', False)]})#, ondelete='cascade'
    obj_type = fields.Selection([
        ('public', "Public"),
        ('private', "private")], default='private', help="HR user just can create public type.", readonly=True)

    is_fix = fields.Boolean(string="Fix Objective?", readonly=True, states={'new': [('readonly', False)]})
    function_name = fields.Text(string="Function", readonly=True, states={'new': [('readonly', False)]})


    # @api.multi
    # def name_get(self):
    #     result = []
    #     for objective in self:
    #         name = "{} ( {} )".format(objective.name, objective.type_of_category_item.name)
    #         result.append((objective.id, name))
    #     return result



    def get_accessible_obj(self):

        result = []
        user = self.env['hr.employee'].search([('user_id', '=', self.env.uid)])
        if self.user_has_groups('ext_evaluation.group_evaluation_admin') or self.user_has_groups('ext_evaluation.group_evaluation_hr'):
            result += self.env['evaluation.objectives'].search([])
        if self.user_has_groups('ext_hr_employee.group_line_manager') :
            result += self.env['evaluation.objectives'].search([('lm_name','=',user.id)])
        if self.user_has_groups('ext_evaluation.group_obj_creator'):
            result += self.env['evaluation.objectives'].search([('lm_name','=',user.line_manager.id)])
        filtered_result_ids = [x.id for x in result]
        return filtered_result_ids

    @api.multi
    def load_eval_obj_action(self):

        valid_item_ids = self.get_accessible_obj()
        action_vals = {
            'name': _('Evaluation Objectives'),
            'domain': [('id', 'in', valid_item_ids)],
            'view_type': 'form',
            'res_model': 'evaluation.objectives',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'view_mode' : 'tree,form',
        }
        return action_vals

    @api.multi
    def unlink(self):
        if self.state in ('running','closed'):
            raise UserError(_('Cannot delete Objective in %s state!')%(self.state))
        return super(EvaluationObjectives, self).unlink()


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(EvaluationObjectives, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        user = self.env['hr.employee'].search([('user_id', '=', self.env.uid)])
        fields = res.get('fields')

        if fields.get('type_of_category_item'):
            if self.user_has_groups('ext_evaluation.group_evaluation_admin') or self.user_has_groups('ext_evaluation.group_evaluation_hr'):
                res['fields']['type_of_category_item']['domain'] = [('is_active','=',True)]
            elif self.user_has_groups('ext_hr_employee.group_line_manager') or self.user_has_groups('ext_evaluation.group_obj_creator'):
            
               res['fields']['type_of_category_item']['domain'] = [('is_fix', '=', False),('is_active','=',True)]


        filtered_users = []
        if fields.get('lm_name'):

            if self.user_has_groups('ext_evaluation.group_evaluation_admin') or self.user_has_groups('ext_evaluation.group_evaluation_hr') :
                filtered_users += self.env['hr.employee'].search([
                    ('is_line_manager', '=', True),('state','=','onboard')
                ])
            if self.user_has_groups('ext_hr_employee.group_line_manager') :
                filtered_users += self.env['hr.employee'].search([
                    ('id', '=', user.id),('is_line_manager','=',True),('state','=','onboard')
                ])
            if self.user_has_groups('ext_evaluation.group_obj_creator'):
                filtered_users += self.env['hr.employee'].search([
                    ('id', '=', user.line_manager.id),('is_line_manager','=',True),('state','=','onboard')
                ])
            filtered_users_ids = [x.id for x in filtered_users]
            res['fields']['lm_name']['domain'] = [('id', 'in', filtered_users_ids)]


        return res


    @api.multi
    @api.onchange('obj_type')
    def onchange_for_obj_type(self):
        
        if self.obj_type =='public':
            self.lm_name = ''
        

    @api.one
    def send_to_running(self):
        if self.obj_type == 'private':
            if not self.lm_name:
                raise ValidationError(_('LM must be set!'))
        self.state = 'running'

    @api.one
    def send_to_close(self):
        self.state = 'closed'

class EvaluationCategory(models.Model):
    _name = "evaluation.category"
    _description = "Evaluation Category"
    _inherit = ['mail.thread']


    name = fields.Char(string='Category Name', required=True , help="Name of evaluation Category for objectives and template.",track_visibility='onchange')
    is_active = fields.Boolean(string='Active',track_visibility='onchange')
    category_items = fields.One2many('evaluation.category.items' ,'category_id',string="Category Items",track_visibility='onchange',copy=True)
    # fix_template = fields.Many2one('evaluation.fix.template', string="Fix Template")
    

    @api.one
    @api.constrains('category_items')
    def _check_percent(self):
        total = 0.0
        category = self.category_items
        for obj in category:
            total += obj.percentage
        if total < 100 or total > 100:
            raise ValidationError(_('Percentages on the category items must be 100 %.'))
        else :
            return True

    # @api.one
    # @api.constrains('is_active')
    # def _is_active(self):
    #     category_obj = self.search([('is_active', '=', True)])
    #     if len(category_obj) > 1:
    #         raise ValidationError(_('Active categoy already exist!'))

    @api.one
    def write(self, vals):
        if self.category_items:
            for items in self.category_items:
                if (vals.get('is_active'))==True:
                    items.is_active = True

                else:
                    items.is_active = False
        return super(EvaluationCategory, self).write(vals)


class EvaluationCategoryItems(models.Model):
    _name = "evaluation.category.items"
    _description = "Evaluation Category Items"
    _inherit = ['mail.thread']

    
    # The relation should be Many2one
    category_id = fields.Many2many('evaluation.category', string="Type of Category")
    is_fix = fields.Boolean(string='Fix',track_visibility='onchange',store=True)
    name = fields.Char(string="Name",track_visibility='onchange')
    percentage = fields.Float(string="Percentage",store=True,track_visibility='onchange')
    # is_active = fields.Boolean(string='Active',track_visibility='onchange',compute='_get_active_status',store=True)
    is_active = fields.Boolean(string='Active',track_visibility='onchange')
    min_count = fields.Integer(string='Min of Count',default=1)

    @api.one
    @api.depends('category_id')
    def _get_active_status(self):
        self.is_active = self.category_id.is_active

    @api.multi
    def name_get(self):
        result = []
        for category in self:
            name = category.name +' (' + str(category.percentage) +'%)'
            result.append((category.id, name))
        return result


