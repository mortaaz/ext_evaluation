# -*- coding: utf-8 -*-
from odoo import api, fields, models,_
from lxml import etree
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning



class EvaluationTemplate(models.Model):
    _name = "evaluation.template"
    _description = "Evaluation Template"
    _inherit = ['mail.thread']



   
    name = fields.Char(string='Template Name', required=True , help="Name of Template.", readonly=True,states={'new': [('readonly', False)]})
    lm_name = fields.Many2one('hr.employee', string="LM Name", required=True,track_visibility='onchange', readonly=True,states={'new': [('readonly', False)]})#,domain=[,('is_line_manager','=',True)]
    manager_name = fields.Many2one('hr.employee', string="Manager Name", readonly=True,states={'new': [('readonly', False)]},domain="[('id', 'in', domain_manager_ids)]")
    state = fields.Selection([
        ('new', 'New'),         
        ('running', 'Running'), 
        ('closed', 'Closed')],
        string='Status', default='new', readonly=True,track_visibility='onchange', copy=False)
    objective_items = fields.One2many('evaluation.template.items' ,'tmp_id',string="Objective Items", readonly=True,states={'new': [('readonly', False)]},copy=True)
    manager_access_right = fields.Boolean(compute="_check_access",readonly=True)
    admin_access_right = fields.Boolean(compute="_check_access",readonly=True)
    domain_manager_ids = fields.Many2many('hr.employee', 'template_manager_rel', 'temp_id','manager_id', string="Manager",compute='_compute_manager_id')


    def get_accessible_templates(self):
        result = []
        user = self.env['hr.employee'].search([('user_id', '=', self.env.uid)])
        if self.user_has_groups('ext_evaluation.group_evaluation_admin'):
            result += self.env['evaluation.template'].search([])
        if self.user_has_groups('ext_hr_employee.group_line_manager') :
            result += self.env['evaluation.template'].search([('lm_name','=',user.id)])
        if self.user_has_groups('ext_evaluation.group_temp_creator'):
            result += self.env['evaluation.template'].search([('lm_name','=',user.line_manager.id)])
        if self.user_has_groups('ext_hr_employee.group_timesheet_approver'):
            result += self.env['evaluation.template'].search([('manager_name', '=', user.id)])
        filtered_result_ids = [x.id for x in result]
        return filtered_result_ids

    @api.multi
    def load_eval_temp_action(self):

        valid_item_ids = self.get_accessible_templates()
        action_vals = {
            'name': _('Evaluation Template'),
            'domain': [('id', 'in', valid_item_ids)],
            'view_type': 'form',
            'res_model': 'evaluation.template',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'view_mode' : 'tree,form',
        }
        return action_vals


    @api.multi
    @api.onchange('lm_name')
    def onchange_manager_name(self):
        filtered_manager = []
        var = []
        self.manager_name = ''
        if self.lm_name:
            
            if self.user_has_groups('ext_evaluation.group_evaluation_admin') or self.user_has_groups('ext_hr_employee.group_line_manager') or self.user_has_groups('ext_evaluation.group_temp_creator'):
                lm = self.env['hr.employee'].search([('line_manager', '=', self.lm_name.id),('state','=','onboard')])
                for emp in lm:
                    var.append(emp.timesheet_approver.id)
                filtered_manager += var
            if self.user_has_groups('ext_hr_employee.group_timesheet_approver'):
                lm = self.env['hr.employee'].search([
                    ('user_id', '=', self.env.uid),('line_manager','=',self.lm_name.id),('state','=','onboard')])
                for emp in lm :
                    var.append(emp.id)
                filtered_manager += var
        

        return {'domain':{'manager_name':[('id', 'in', filtered_manager)]}}


    def _compute_manager_id(self):

        filtered_manager = []
        var = []
        self.manager_name = ''
        if self.lm_name:
            if self.user_has_groups('ext_evaluation.group_evaluation_admin') or self.user_has_groups('ext_hr_employee.group_line_manager') or self.user_has_groups('ext_evaluation.group_temp_creator'):
                lm = self.env['hr.employee'].search([('line_manager', '=', self.lm_name.id),('state','=','onboard')])
                for emp in lm:
                    var.append(emp.timesheet_approver.id)
                filtered_manager += var
            if self.user_has_groups('ext_hr_employee.group_timesheet_approver'):
                lm = self.env['hr.employee'].search([
                    ('user_id', '=', self.env.uid),('line_manager','=',self.lm_name.id),('state','=','onboard')])
                for emp in lm :
                    var.append(emp.id)
                filtered_manager += var
            self.domain_manager_ids = filtered_manager

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(EvaluationTemplate, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        user = self.env['hr.employee'].search([('user_id', '=', self.env.uid)])
        fields = res.get('fields')
        filtered_users = []
        if fields.get('lm_name'):

            if self.user_has_groups('ext_evaluation.group_evaluation_admin')  :
                filtered_users += self.env['hr.employee'].search([('is_line_manager', '=', True),('state','=','onboard')])

            if self.user_has_groups('ext_hr_employee.group_line_manager') :
                filtered_users += self.env['hr.employee'].search([('id', '=', user.id),('is_line_manager','=',True),('state','=','onboard')])

            if self.user_has_groups('ext_evaluation.group_temp_creator'):
                filtered_users += self.env['hr.employee'].search([
                    ('id', '=', user.line_manager.id),('is_line_manager','=',True),('state','=','onboard')])

            if self.user_has_groups('ext_hr_employee.group_timesheet_approver'):
                filtered_users += self.env['hr.employee'].search([
                    ('id', '=', user.line_manager.id),('is_line_manager','=',True),('state','=','onboard')])

            filtered_users_ids = [x.id for x in filtered_users]
            res['fields']['lm_name']['domain'] = [('id', 'in', filtered_users_ids)]

        return res


    @api.one
    @api.depends('name')
    def _check_access(self):
        for record in self:
            self.env.cr.execute("""select name from (select gid from res_groups_users_rel where uid=%s)gu
            join (select id,name from res_groups)g on g.id=gu.gid where name ~* 'Timesheet Approver';""", (self.env.uid,))
            tm = self.env.cr.fetchone()
            if tm:
                record.manager_access_right = True

            self.env.cr.execute("""select g.name from (select gid from res_groups_users_rel where uid=%s)gu
            join (select id,name,category_id from res_groups)g on g.id=gu.gid join 
            (select id,name from ir_module_category)m on m.id = g.category_id
            where g.name ~* 'Line Manager' or g.name ~* 'Admin' and m.name ~* 'Evaluation' or g.name ~* 'Template Creator' and m.name ~* 'Evaluation' """, (self.env.uid,))
            admin = self.env.cr.fetchone()
            if admin:
                record.admin_access_right = True


    @api.multi
    def unlink(self):
        if self.state in ('running','closed'):
            raise UserError(_('Cannot delete Template in %s state!')%(self.state))
        return super(EvaluationTemplate, self).unlink()

  
    @api.multi
    def send_to_running(self):
        if not self.objective_items:
            raise UserError(_('You must set objectives for template!'))
        if self.objective_items:
            percentage = 0.0
            eval_cat = []
            
            
            wizard_id = self.env['wizard.calculate.temp.item'].search([('tmp_id', '=', self.id)])
            if not wizard_id :
                wizard_id = self.env['wizard.calculate.temp.item'].create({'tmp_id':self.id })
            self.env.cr.execute("select distinct category_id from evaluation_template_items where tmp_id=%s", (self.id,))
            res = self.env.cr.fetchall()
            active_category_items = self.env['evaluation.category.items'].search([('is_active', '=', True)])
            category_item_name = [x.id for x in active_category_items]
            wizard_obj = self.env['wizard.calculate.temp.item'].search([('id', '=', wizard_id.id)])
            for category_id in res:
                category_obj = self.env['evaluation.category.items'].search([('id', '=', category_id)])
                percent = category_obj.percentage
                min_count = category_obj.min_count
                self.env.cr.execute("select count(*) from evaluation_template_items where category_id=%s and tmp_id=%s", (category_id,self.id,))
                count_result = self.env.cr.fetchone()[0]
                self.env.cr.execute("select sum(weight) from evaluation_template_items where category_id=%s and tmp_id=%s", (category_id,self.id,))
                result = self.env.cr.fetchone()[0]
                eval_cat.append(category_obj.id)
                self.env['calculate.template.items'].create({'calc_id':wizard_id.id,
                                                        'category_id': category_id,
                                                        'weight':result,
                                                        'count':count_result })
            self.env.cr.execute("select sum(weight) from evaluation_template_items where tmp_id=%s", (self.id,))
            final_result = self.env.cr.fetchone()[0]
            wizard_obj.update({'description':("Your template weight is %s of 100 percent" % (final_result))})
            if final_result>100:
                raise UserError(_('Template weight is %s which is more than 100 percent!') % (final_result))

            return {
                'name': ('Calculation objectives'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'wizard.calculate.temp.item',
                'res_id': wizard_id.id,
                'target': 'new'
            }
        # self.state = 'running'


    @api.one
    def send_to_close(self):
        self.state = 'closed'

    @api.multi
    @api.onchange('lm_name')
    def onchange_for_manager_name(self):
        
        if self.lm_name :
            self.manager_name = ''
    


class EvaluationTemplateItems(models.Model):
    _name = "evaluation.template.items"
    _description = "Evaluation Template Items"

    category_id = fields.Many2one('evaluation.category.items', string="Category Name",domain=[('is_active','=',True)],  required=True)
    obj_item = fields.Many2one('evaluation.objectives', string="Objective Name",required=True)
    tmp_id = fields.Many2one('evaluation.template', string="Template Name",  required=True)
    weight = fields.Float(string="Weight")
    target = fields.Float(string="Target")
    description = fields.Text(string="Description")

    @api.multi
    @api.onchange('category_id','tmp_id')
    def onchange_category_items(self):

        filtered_objective = []
        general_cond = []
        spcific_cond = []
        if self.category_id:
            self.obj_item = ''
            general_cond += self.env['evaluation.objectives'].search([('type_of_category_item', '=', self.category_id.id),('state', '=','running')])
            spcific_cond += self.env['evaluation.objectives'].search([('lm_name', '=', self.tmp_id.lm_name.id)])
            spcific_cond += self.env['evaluation.objectives'].search([('obj_type','=','public')])
            
            general_cond = [x.id for x in general_cond]
            spcific_cond = [x.id for x in spcific_cond]
            filtered_objective = list(set(general_cond).intersection(spcific_cond))
            
        return {'domain':{'obj_item':[('id', 'in', filtered_objective)]}}



class CalculateTemplateItems(models.Model):
    _name = "calculate.template.items"
    _description = "Calculate Template Items"


    calc_id = fields.Many2one('wizard.calculate.temp.item', string="Wizard Name")
    category_id = fields.Many2one('evaluation.category.items', string="Category Name") 
    weight = fields.Float(string="Sum of Weight") 
    count = fields.Integer(string="count of objective")

class WizardCalculateTempItem(models.Model):
    _name = 'wizard.calculate.temp.item'

    description = fields.Char(string="Description",readonly=True)
    calc_objectives_weight = fields.One2many('calculate.template.items','calc_id' ,string="Calc Objectives",copy=True,readonly=True)
    tmp_id = fields.Many2one('evaluation.template',string="template ID")

    @api.multi
    def send_to_running(self):
        self.tmp_id.state = 'running'
        return True
