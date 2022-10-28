# -*- coding: utf-8 -*-
from typing import List
from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError, UserError
import base64
from base64 import b64encode
from urllib import parse
import http.client
import xmlrpc.client
import ssl
import json
import logging
_logger = logging.getLogger(__name__)





class StaffEvaluationCpiSpiScore(models.Model):
    _name = "evaluation.cpi_spi_raw_score"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=True)
    evaluation_period_id = fields.Many2one('evaluation.period', string="Period", required=True, readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done')
        ], 
    string='Status', default='draft', readonly=True, track_visibility='onchange', copy=False)
    cpi_spi_score_line = fields.One2many('evaluation.cpi_spi_raw_score_line', 'parent_id', string="Lines")
    
    def open_upload_page(self):
        return {
            "name": _("Upload Data"),
            "type": 'ir.actions.act_window',
            "res_model": 'evaluation.upload_cpi_spi_wizard',
            "views": [[False, "form"]],
            "target": 'new',
            "context": {
                'active_id': self.id,
                'active_model': 'evaluation.cpi_spi_raw_score',
            },
        }

    def send_to_done(self):
        self.state = 'done'
        for item in self.cpi_spi_score_line:
            item.send_to_done()
        
    
    @api.multi
    def unlink(self):
        for obj in self:
            if obj.state != 'draft':
                raise UserError(_('You Can Only Delete CPI / SPI Record which is in Draft State!'))
            for item in obj.cpi_spi_score_line:
                if item.state !='draft':
                    raise UserError(_('You Can Only Delete CPI / SPI Record Item which is in Draft State!'))
        return super(StaffEvaluationCpiSpiScore, self).unlink()


class StaffEvaluationCpiSpiScoreLine(models.Model):
    _name = "evaluation.cpi_spi_raw_score_line"

    program_manager_id = fields.Many2one('hr.employee', string="Program Manager")
    project_manager_id = fields.Many2one('hr.employee', string="Project Manager")

    # program_id = fields.Many2one('ext.analytic.account', string="Program", readonly=True)
    # project_id = fields.Many2one('ext.analytic.account', string="Project", readonly=True)
    
    program_name = fields.Char(string="Program Name", required = True)
    project_name = fields.Char(string="Project Name", required = True)
    wbs_id = fields.Many2one('ext.analytic.account', string="WBS", readonly=True, required=True)
    
    pgmo_id = fields.Many2one('hr.employee', string="PGMO", readonly=True)
    pmo_id = fields.Many2one('hr.employee', string="PMO", readonly=True)
    spi_global = fields.Float('SPI Global')
    cpi_global = fields.Float('CPI Global')
    spi_quarterly = fields.Float('SPI Quarterly')
    cpi_quarterly = fields.Float('CPI Quarterly')
    spi_team = fields.Float('SPI Team')
    ofi = fields.Float('OFI')
    project_staff_target = fields.Float('Project/Staff Target')
    parent_id = fields.Many2one('evaluation.cpi_spi_raw_score', string="Parent", required=True)
    evaluation_period_id = fields.Many2one('evaluation.period', string="Period", required=True, readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done')
        ], 
    string='Status', default='draft', readonly=True, track_visibility='onchange', copy=False)


    _sql_constraints = [
        ('project_period_uniq', 'unique (evaluation_period_id, wbs_id)', 'Combination of Period and Project must be unique!'),
    ]

    def send_to_done(self):
        self.state = 'done'


class StaffEvaluationOrganizationScore(models.Model):
    _name="evaluation.organization_raw_score"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=True)
    evaluation_period_id = fields.Many2one('evaluation.period', string="Period", required=True, readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done')
        ], 
    string='Status', default='draft', readonly=True, track_visibility='onchange', copy=False)
    score = fields.Float(string="Score")
    description = fields.Text(string="Description")

    _sql_constraints = [
        ('period_unique', 'unique (evaluation_period_id)', 'For each period, You can create only one record!'),
    ]

    def send_to_done(self):
        self.env.cr.execute("""
            UPDATE evaluation_evaluation SET organization_score = {self.score} WHERE period_id = {self.evaluation_period_id.id}
        """.format(**locals()))
        self.state = 'done'


class StaffEvaluationUploadCpiSpiWizard(models.TransientModel):
    _name="evaluation.upload_cpi_spi_wizard"

    attachment = fields.Binary(string='Attachments')

    def get_emp_from_staff_id(self, staff_id):
        self.env.cr.execute("""
                SELECT id FROM hr_employee WHERE staff_id= '{staff_id}'
                """.format(**locals()))
        data = self.env.cr.dictfetchall()
        if not data:
            raise UserError(_('Employee with staff ID:{staff_id} does not found'.format(**locals())))
        return data[0]['id']

    @api.one
    def upload_data(self):
        parent_obj = self.env['evaluation.cpi_spi_raw_score'].browse(self._context.get('active_id',False))

        file = base64.b64decode(self.attachment)
        file_string = file.decode('utf-8')
        file_string = file_string.split('\n')

        header = file_string[0].split(',')
        content = []
        for item in file_string[1:]:
            content.append(
                {h: b for h,b in zip(header, item.split(','))}
            )

        for row in content:
            if 'WBS Code' in row:
                
                input_wbs_code = row['WBS Code']
                query = """
                    SELECT id FROM ext_analytic_account WHERE UPPER(REPLACE(name, ' ', '')) = UPPER(REPLACE('{}', ' ', ''))
                    AND type_id = 'project'
                """.format(row['WBS Code'])
                self.env.cr.execute(query)
                wbs_query_result =self.env.cr.dictfetchall()
                if len(wbs_query_result) == 0:
                    raise UserError(_('Related Analytic Account Not Found:{input_wbs_code}'.format(**locals())))
                wbs_id = wbs_query_result[0]['id']

                self.env['evaluation.cpi_spi_raw_score_line'].create({
                    'parent_id':parent_obj.id,
                    'program_manager_id':self.get_emp_from_staff_id(row['Program Manager']),
                    'project_manager_id':self.get_emp_from_staff_id(row['Project Manager']),
                    'program_name':row['Program'],
                    'project_name':row['Project Name'],
                    'pgmo_id':self.get_emp_from_staff_id(row['PgMO']),
                    'pmo_id':self.get_emp_from_staff_id(row['PMO']),
                    'spi_global':row['SPI Global'],
                    'cpi_global':row['CPI Global'],
                    'spi_quarterly':row['SPI Quarterly'],
                    'cpi_quarterly':row['CPI Quarterly'],
                    'spi_team':row['SPI Team'],
                    'ofi':row['OFI'],
                    'project_staff_target': row['Project/Staff Target'],
                    'state':'draft',
                    'evaluation_period_id': parent_obj.evaluation_period_id.id,
                    'wbs_id':wbs_id,
                })


class EvaluationobjectiveGeneratorLine(models.Model):
    _name = 'evaluation.objective_generator_line'

    generator_id = fields.Many2one('evaluation.objective_generator', string="Generator")
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    objective_id = fields.Many2one('evaluation.objectives', string="Objective")
    period_id = fields.Many2one('evaluation.period', string="Period")
    score = fields.Float(string="Score")
    evaluation_item = fields.Many2one('evaluation.items', string="Evaluation Item")
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done')
        ], 
    string='Status', default='draft', readonly=True, track_visibility='onchange', copy=False)


class EvaluationobjectiveGenerator(models.Model):
    _name = 'evaluation.objective_generator'

    name = fields.Char(string="Name", required=True)
    evaluation_period_id = fields.Many2one('evaluation.period', string="Period", required=True, readonly=True)
    objective_ids = fields.Many2many('evaluation.objectives')
    objective_item_ids = fields.One2many('evaluation.objectives.items', 'generator_id', name="Objective Items")
    line_ids = fields.One2many('evaluation.objective_generator_line', 'generator_id', name="Lines")    
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done')
        ], 
    string='Status', default='draft', readonly=True, track_visibility='onchange', copy=False)
    
    customer_satisfaction_period = fields.Selection(selection=lambda self: self._get_customer_satisfactions(), string="Customer Satisfaction")

    show_customer_satisfactions = fields.Boolean(string="Show Customer Satisfaction", readonly=True, default=False)
    system_description = fields.Text(string="System Description", readonly=True)
    unique_objective_name = fields.Char(string="Unique Objective Name", readonly=True)

    description_mapper = {
        'CPI':"""
            Make Sure that CPI lines have been Imported and is in "Done" State
            Make Sure that All related Employees have WTA Periodic Weight and is in "Publish" State
            """,
        'SPI':"""
            Make Sure that SPI lines have been Imported and is in "Done" State
            Make Sure that All related Employees have WTA Periodic Weight and is in "Publish" State
            """,
        'Internal Satisfaction':"""

        """,
        'Customer Satisfaction':"""
            Choose between Questionaries and fetch WBS scores
        """,
        'CEO Satisfaction':"""
            Make Sure Organization Score has been submitted and is in "Done" State
        """,

    }

    
    def check_evaluation_period(self):
        if self.evaluation_period_id.is_active != True:
            raise UserError(_('performace period {} is not in active state'.format(self.evaluation_period_id.name)))


    
    @api.multi
    def unlink(self):
        for obj in self:
            if obj.state != 'draft':
                raise UserError(_('You Can Only Delete Objective Generator which is in Draft State!'))
        return super(EvaluationobjectiveGenerator, self).unlink()


    def send_to_done(self):
        self.check_evaluation_period()
        objectives_ids = [x.id for x in self.objective_ids]
        objectives_ids += [-1]
        objectives_ids = tuple(objectives_ids)

        evaluation_rec = self.env['evaluation.items.manager']
        for item in self.line_ids:
            score = item.score
            self.env.cr.execute("""
                UPDATE evaluation_items SET lm_score = {score}, manager_score = {score}, lm_target=100, manager_target=100 WHERE eval_id IN (
                    SELECT id FROM evaluation_evaluation WHERE employee_id = {item.employee_id.id} AND period_id = {self.evaluation_period_id.id}
                ) AND obj_item in {objectives_ids}
            """.format(**locals()))

            evaluation_rec.create({'category_id': item.objective_id.type_of_category_item.id, #evaluation.category.items
                                        'obj_item': item.objective_id.id, #evaluation.objectives
                                        'eval_id':item.evaluation_item.eval_id.id, #evaluation.evaluation
                                        'weight':item.evaluation_item.weight, 
                                        'target':item.evaluation_item.target,
                                        'ind_target_result':score,
                                        'ind_target':score,
                                        'manager_target':score,
                                        'manager_score':score,
                                        'lm_target':score,
                                        'lm_score':score,
                                })

            self.env.cr.execute("""
            UPDATE evaluation_objectives_items SET generator_id = {self.id} WHERE obj_item IN {objectives_ids}
            AND obj_item in {objectives_ids} AND eval_id IN (
                SELECT id FROM evaluation_evaluation WHERE employee_id = {item.employee_id.id} AND period_id = {self.evaluation_period_id.id}
            )
            """.format(**locals()))
            item.write({'state': 'done'})
        self.state='done'
        return True
        

    @api.multi
    def write(self, vals):
        if 'objective_ids' in vals:
            objective_ids = vals['objective_ids'][0][2]
            if objective_ids:
                objective_name = self.env['evaluation.objectives'].browse(objective_ids[0])[0].name
                if objective_name in ('Customer Satisfaction', ):
                    vals.update({'show_customer_satisfactions': True})
                else:
                    vals.update({'show_customer_satisfactions': False})
            else:
                vals.update({'show_customer_satisfactions': False})
        res = super(EvaluationobjectiveGenerator, self).write(vals)
        return res



    @api.onchange('objective_ids')
    def _onchange_objectives(self):
        all_objective_functions = []
        for obj in self.objective_ids:
            all_objective_functions.append(obj.name)
        
        all_objective_functions = list(set(all_objective_functions))
        if len(all_objective_functions) > 1:
            raise UserError(_("Source Objectives have to has same function names"))
        if len(all_objective_functions) == 1:
            objective_name = all_objective_functions[0]
            self.unique_objective_name = objective_name

            if objective_name in ('Customer Satisfaction', ):
                self.show_customer_satisfactions = True
            else:
                self.show_customer_satisfactions = False
            
            
            if str(objective_name) in self.description_mapper:
                self.system_description = self.description_mapper[str(objective_name)]
            else:
                self.description_mapper = ""

    def generate_objectives(self):
        # Get Objective Type and decide what function should call
        self.check_evaluation_period()
        for objective in self.objective_ids:
            function_name = objective.function_name
            if not function_name:
                raise UserError(_("You dont have assign any function for this objective"))
            
            if not hasattr(EvaluationobjectiveGenerator, function_name):
                raise UserError(_("for this type of objective, we have no parser! "))
            getattr(EvaluationobjectiveGenerator, function_name)(self)
        return True

    #Get customer saticfaction list from BI Server
    def _get_customer_satisfactions(self):
        result = []
        # return result
        try:
            conn = http.client.HTTPConnection("172.26.8.146", 8080)
            payload = ''
            headers = { 
                }
            conn.request("GET", "/ords/report/BI/GetSeasonList", payload, headers, )
            res = conn.getresponse()
            datas = res.read()
            datas = json.loads(datas)
            if "items" in datas:
                for item in datas["items"]:
                    if "season_id" in item and "season_name" in item:
                        result.append((item["season_id"], item["season_name"]))
        except:
            _logger.error("""
                we are try to fetch seasons but,
                An exception occured during connecting to BI Server""")
        finally:
            return result
    
    def generate_customer_satisfaction(self ):
        result = []
        conn = http.client.HTTPConnection("172.26.8.146", 8080)
        payload = ''
        headers = { 
            }
        conn.request("GET", "/ords/report/BI/GetData/{}".format(self.customer_satisfaction_period), payload, headers, )
        res = conn.getresponse()
        datas = res.read()
        datas = json.loads(datas)

        self.check_evaluation_period()
        for objective in self.objective_ids:
            employees = self.get_employees(objective, self.evaluation_period_id)
            # cpi_list = self.env['evaluation.cpi_spi_raw_score_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id), ('state', '=', 'done')])
            customer_scores = {}
            for data in datas['items']:
                # , ('type_id', '=', 'project')
                analytic_obj = self.env['ext.analytic.account'].search([('full_name', 'like', data['wbs_id']), ('type_id', '=', 'project')])
                customer_scores[analytic_obj] = data['weight']
            wta_list = self.env['evaluation.periodic_weight_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id),
                ('employee_id', 'in', employees), ('state', '=', 'publish')])

            employee_customer_statisfaction = {}
            for wta in wta_list:
                emp = wta.employee_id
                emp_project_id = wta.project_id
                emp_charge_perc = wta.value
                emp_project_name = emp_project_id.short_name
                emp_name = emp.name

                duplicate_emp = self.env['evaluation.objective_generator_line'].search([('employee_id', '=', emp.id), 
                    ('objective_id', '=', objective.id), ('period_id', '=', self.evaluation_period_id.id)])
                
                if len(duplicate_emp) == 0:
                    if emp_project_id not in customer_scores:
                        continue
                    
                    project_statisfaction_value = customer_scores[emp_project_id]
                    statisfaction_value = emp_charge_perc * project_statisfaction_value

                    if emp.id not in employee_customer_statisfaction:
                        employee_customer_statisfaction[emp.id] = statisfaction_value
                    else:
                        employee_customer_statisfaction[emp.id] += statisfaction_value

            for emp in employee_customer_statisfaction:
                self.env.cr.execute("""
                SELECT id FROM evaluation_items WHERE eval_id IN (
                    SELECT id FROM evaluation_evaluation WHERE employee_id = {} and period_id = {})
                AND obj_item = {}
                """.format(emp, self.evaluation_period_id.id, objective.id))


                eval_item_id = self.env.cr.dictfetchall()
                if eval_item_id:
                    eval_item_id = eval_item_id[0]['id']
                    self.env['evaluation.objective_generator_line'].create({
                        'generator_id':self.id,
                        'employee_id':emp,
                        'objective_id':objective.id,
                        'period_id': self.evaluation_period_id.id,
                        'score':employee_customer_statisfaction[emp],
                        'evaluation_item':eval_item_id,
                        'state':'draft',
                    })
        return True

        return result


    def get_employees(self, objective, period_id):
        self.check_evaluation_period()
        result = []
        query = """
        select emp.id from
        (select * from hr_employee where evaluation_enable = True) emp
        INNER join
        (select * from evaluation_evaluation WHERE period_id={period_id.id}) as eval
        on emp.id = eval.employee_id
        INNER join
        (select * from evaluation_objectives_items) as obj_item
        on obj_item.eval_id = eval.id
        INNER JOIN 
        (SELECT * FROM evaluation_objectives WHERE name = '{objective.name}') as obj
        on obj.id = obj_item.obj_item""".format(**locals())
        self.env.cr.execute(query)
        
        for emp in self.env.cr.dictfetchall():
            result.append(emp['id'])

        return result


    def generate_cpi_global(self):
        self.check_evaluation_period()
        for objective in self.objective_ids:
            employees = self.get_employees(objective, self.evaluation_period_id)
            cpi_list = self.env['evaluation.cpi_spi_raw_score_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id), ('state', '=', 'done')])
            cpi_scores = {x.wbs_id:x.cpi_global for x in cpi_list}
            wta_list = self.env['evaluation.periodic_weight_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id),
                ('employee_id', 'in', employees), ('state', '=', 'publish')])
            employee_cpis = {}

            for wta in wta_list:
                emp = wta.employee_id
                emp_project_id = wta.project_id
                emp_charge_perc = wta.value
                emp_project_name = emp_project_id.short_name
                emp_name = emp.name

                duplicate_emp = self.env['evaluation.objective_generator_line'].search([('employee_id', '=', emp.id), 
                    ('objective_id', '=', objective.id), ('period_id', '=', self.evaluation_period_id.id)])
                
                if len(duplicate_emp) == 0:
                    if emp_project_id not in cpi_scores:
                        raise UserError(_("""employee {emp_name} has been charged in {emp_project_name}. 
                        and there is no CPI Score for this project or related record is not in 'done' state!""".format(**locals())))
                    
                    project_cpi_value = cpi_scores[emp_project_id]
                    cpi_value = emp_charge_perc * project_cpi_value

                    if emp.id not in employee_cpis:
                        employee_cpis[emp.id] = cpi_value
                    else:
                        employee_cpis[emp.id] += cpi_value
            for emp in employee_cpis:
                self.env.cr.execute("""
                SELECT id FROM evaluation_items WHERE eval_id IN (
                    SELECT id FROM evaluation_evaluation WHERE employee_id = {} and period_id = {})
                AND obj_item = {}
                """.format(emp, self.evaluation_period_id.id, objective.id))
                
                eval_item_id = self.env.cr.dictfetchall()
                if eval_item_id:
                    eval_item_id = eval_item_id[0]['id']
                    self.env['evaluation.objective_generator_line'].create({
                        'generator_id':self.id,
                        'employee_id':emp,
                        'objective_id':objective.id,
                        'period_id': self.evaluation_period_id.id,
                        'score':employee_cpis[emp]*100,
                        'evaluation_item':eval_item_id,
                        'state':'draft',
                    })
        return True

    def generate_project_staff_target(self):
        self.check_evaluation_period()
        for objective in self.objective_ids:
            employees = self.get_employees(objective, self.evaluation_period_id)
            cpi_spi_list = self.env['evaluation.cpi_spi_raw_score_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id), ('state', '=', 'done')])
            ps_target_scores = {x.wbs_id:x.project_staff_target for x in cpi_spi_list}
            wta_list = self.env['evaluation.periodic_weight_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id),
                ('employee_id', 'in', employees), ('state', '=', 'publish')])
            employee_ps_targets = {}

            for wta in wta_list:
                emp = wta.employee_id
                emp_project_id = wta.project_id
                emp_charge_perc = wta.value
                emp_project_name = emp_project_id.short_name
                emp_name = emp.name

                duplicate_emp = self.env['evaluation.objective_generator_line'].search([('employee_id', '=', emp.id), 
                    ('objective_id', '=', objective.id), ('period_id', '=', self.evaluation_period_id.id)])
                
                if len(duplicate_emp) == 0:
                    if emp_project_id not in ps_target_scores:
                        raise UserError(_("""employee {emp_name} has been charged in {emp_project_name}. 
                        and there is no Project/Staff Target Score for this project or related record is not in 'done' state!""".format(**locals())))
                    
                    ps_target_value = ps_target_scores[emp_project_id]
                    cpi_value = emp_charge_perc * ps_target_value

                    if emp.id not in employee_ps_targets:
                        employee_ps_targets[emp.id] = cpi_value
                    else:
                        employee_ps_targets[emp.id] += cpi_value
            for emp in employee_ps_targets:
                self.env.cr.execute("""
                SELECT id FROM evaluation_items WHERE eval_id IN (
                    SELECT id FROM evaluation_evaluation WHERE employee_id = {} and period_id = {})
                AND obj_item = {}
                """.format(emp, self.evaluation_period_id.id, objective.id))
                
                eval_item_id = self.env.cr.dictfetchall()
                if eval_item_id:
                    eval_item_id = eval_item_id[0]['id']
                    self.env['evaluation.objective_generator_line'].create({
                        'generator_id':self.id,
                        'employee_id':emp,
                        'objective_id':objective.id,
                        'period_id': self.evaluation_period_id.id,
                        'score':employee_ps_targets[emp]*100,
                        'evaluation_item':eval_item_id,
                        'state':'draft',
                    })
        return True


    def generate_spi_global(self):
        self.check_evaluation_period()
        for objective in self.objective_ids:
            employees = self.get_employees(objective, self.evaluation_period_id)
            spi_list = self.env['evaluation.cpi_spi_raw_score_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id), ('state', '=', 'done')])
            spi_scores = {x.wbs_id:x.spi_global for x in spi_list}
            wta_list = self.env['evaluation.periodic_weight_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id),
                ('employee_id', 'in', employees), ('state', '=', 'publish')])
            employee_spis = {}

            for wta in wta_list:
                emp = wta.employee_id
                emp_project_id = wta.project_id
                emp_charge_perc = wta.value
                emp_project_name = emp_project_id.short_name
                emp_name = emp.name
                duplicate_emp = self.env['evaluation.objective_generator_line'].search([('employee_id', '=', emp.id), 
                    ('objective_id', '=', objective.id), ('period_id', '=', self.evaluation_period_id.id)])
                
                if len(duplicate_emp) == 0:
                    if emp_project_id not in spi_scores:
                        raise UserError(_("""employee {emp_name} has been charged in {emp_project_name}. 
                        and there is no SPI Score for this project or related record is not in 'done' state!""".format(**locals())))
                    
                    project_spi_value = spi_scores[emp_project_id]
                    spi_value = emp_charge_perc * project_spi_value

                    if emp.id not in employee_spis:
                        employee_spis[emp.id] = spi_value
                    else:
                        employee_spis[emp.id] += spi_value


            for emp in employee_spis:
                self.env.cr.execute("""
                SELECT id FROM evaluation_items WHERE eval_id IN (
                    SELECT id FROM evaluation_evaluation WHERE employee_id = {} and period_id = {})
                AND obj_item = {}
                """.format(emp, self.evaluation_period_id.id, objective.id))
                
                eval_item_id = self.env.cr.dictfetchall()
                if eval_item_id:
                    eval_item_id = eval_item_id[0]['id']

                    self.env['evaluation.objective_generator_line'].create({
                        'generator_id':self.id,
                        'employee_id':emp,
                        'objective_id':objective.id,
                        'period_id': self.evaluation_period_id.id,
                        'score':employee_spis[emp]*100,
                        'evaluation_item':eval_item_id,
                        'state':'draft',

                    })
        return True


    def generate_spi_team(self):
        self.check_evaluation_period()
        for objective in self.objective_ids:
            employees = self.get_employees(objective, self.evaluation_period_id)
            spi_list = self.env['evaluation.cpi_spi_raw_score_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id), ('state', '=', 'done')])
            spi_scores = {x.wbs_id:x.spi_team for x in spi_list}
            wta_list = self.env['evaluation.periodic_weight_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id),
                ('employee_id', 'in', employees), ('state', '=', 'publish')])
            employee_spis = {}

            for wta in wta_list:
                emp = wta.employee_id
                emp_project_id = wta.project_id
                emp_charge_perc = wta.value
                emp_project_name = emp_project_id.short_name
                emp_name = emp.name
                duplicate_emp = self.env['evaluation.objective_generator_line'].search([('employee_id', '=', emp.id), 
                    ('objective_id', '=', objective.id), ('period_id', '=', self.evaluation_period_id.id)])
                
                if len(duplicate_emp) == 0:
                    if emp_project_id not in spi_scores:
                        raise UserError(_("""employee {emp_name} has been charged in {emp_project_name}. 
                        and there is no SPI Score for this project or related record is not in 'done' state!""".format(**locals())))
                    
                    project_spi_value = spi_scores[emp_project_id]
                    spi_value = emp_charge_perc * project_spi_value

                    if emp.id not in employee_spis:
                        employee_spis[emp.id] = spi_value
                    else:
                        employee_spis[emp.id] += spi_value


            for emp in employee_spis:
                query = """
                SELECT id FROM evaluation_items WHERE eval_id IN (
                    SELECT id FROM evaluation_evaluation WHERE employee_id = {} and period_id = {})
                AND obj_item = {}
                """.format(emp, self.evaluation_period_id.id, objective.id)

                self.env.cr.execute(query)

                
                eval_item_id = self.env.cr.dictfetchall()
                if eval_item_id:
                    eval_item_id = eval_item_id[0]['id']

                    self.env['evaluation.objective_generator_line'].create({
                        'generator_id':self.id,
                        'employee_id':emp,
                        'objective_id':objective.id,
                        'period_id': self.evaluation_period_id.id,
                        'score':employee_spis[emp]*100,
                        'evaluation_item':eval_item_id,
                        'state':'draft',

                    })
        return True


    def generate_ofi(self):
        self.check_evaluation_period()
        for objective in self.objective_ids:
            employees = self.get_employees(objective, self.evaluation_period_id)
            spi_list = self.env['evaluation.cpi_spi_raw_score_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id), ('state', '=', 'done')])
            spi_scores = {x.wbs_id:x.ofi for x in spi_list}
            wta_list = self.env['evaluation.periodic_weight_line'].search([('evaluation_period_id', '=', self.evaluation_period_id.id),
                ('employee_id', 'in', employees), ('state', '=', 'publish')])
            employee_spis = {}

            for wta in wta_list:
                emp = wta.employee_id
                emp_project_id = wta.project_id
                emp_charge_perc = wta.value
                emp_project_name = emp_project_id.short_name
                emp_name = emp.name
                duplicate_emp = self.env['evaluation.objective_generator_line'].search([('employee_id', '=', emp.id), 
                    ('objective_id', '=', objective.id), ('period_id', '=', self.evaluation_period_id.id)])
                
                if len(duplicate_emp) == 0:
                    if emp_project_id not in spi_scores:
                        raise UserError(_("""employee {emp_name} has been charged in {emp_project_name}. 
                        and there is no SPI Score for this project or related record is not in 'done' state!""".format(**locals())))
                    
                    project_spi_value = spi_scores[emp_project_id]
                    spi_value = emp_charge_perc * project_spi_value

                    if emp.id not in employee_spis:
                        employee_spis[emp.id] = spi_value
                    else:
                        employee_spis[emp.id] += spi_value


            for emp in employee_spis:
                self.env.cr.execute("""
                SELECT id FROM evaluation_items WHERE eval_id IN (
                    SELECT id FROM evaluation_evaluation WHERE employee_id = {} and period_id = {})
                AND obj_item = {}
                """.format(emp, self.evaluation_period_id.id, objective.id))


                eval_item_id = self.env.cr.dictfetchall()
                if eval_item_id:
                    eval_item_id = eval_item_id[0]['id']

                    self.env['evaluation.objective_generator_line'].create({
                        'generator_id':self.id,
                        'employee_id':emp,
                        'objective_id':objective.id,
                        'period_id': self.evaluation_period_id.id,
                        'score':employee_spis[emp]*100,
                        'evaluation_item':eval_item_id,
                        'state':'draft',

                    })
                    
        return True


    # def test_to_connect_pars(self):
    #     self.check_evaluation_period()

    #     conn = http.client.HTTPConnection("localhost", 8000)
    #     payload = ''
    #     userAndPass = b64encode(b"username:password").decode("ascii")
    #     headers = { 
    #         'Authorization' : 'Basic %s' %  userAndPass,
    #         }
    #     param_dict = {
    #         'kpi_names': 'BCCH_DownTime_Duration(sec)(Eric_Cell)',
    #         'agg_type': 'HOURLY',
    #         'ne_names': 'KJ',
    #         'start_date': '20210427',
    #         'end_date':'20210427',
    #         'start_hour':'12',
    #         'end_hour':'13'
    #     }
    #     param_uri = parse.urlencode(param_dict)
    #     conn.request("GET", "/external-api/kashef/?"+param_uri, payload, headers, )
    #     res = conn.getresponse()
    #     data = res.read()
    #     print(data.decode("utf-8"))

    #     return True

    def generate_ceo_satisfaction(self):
        self.check_evaluation_period()
        
        employees = self.get_employees(self.objective_type_id)
        ceo_satisfaction_obj = self.env['evaluation.organization_raw_score'].search([('state', '=', 'done'), ('evaluation_period_id', '=', self.evaluation_period_id.id)])
        if not ceo_satisfaction_obj:
            raise UserError(_("No Record found related to ceo statisfaction or it is not in 'done' state!"))
        for emp in employees:

            # self.env['evaluation.objective'].create({
            #     'employee_id':emp,
            #     'objective_type_id':self.objective_type_id.id,
            #     'period_id':self.evaluation_period_id.id,
            #     'score':ceo_satisfaction_obj[0].score,
            #     'generator_id':self.id,
            #     'state':'draft',
            # })

            self.env.cr.execute("""
            SELECT id FROM evaluation_items WHERE eval_id IN (
                SELECT id FROM evaluation_evaluation WHERE employee_id = {} and period_id = {})
            AND obj_item = {}
            """.format(emp.id, self.evaluation_period_id.id, self.objective_id.id))
            eval_item_id = self.env.cr.dictfetchall()[0]['id']

            self.env['evaluation.objective_generator_line'].create({
                'generator_id':self.id,
                'employee_id':emp,
                'objective_id':self.objective_id.id,
                'period_id': self.evaluation_period_id.id,
                'score':ceo_satisfaction_obj[0].score,
                'evaluation_item':eval_item_id,
                'state':'draft',

            })
            
        return True

    def import_data_to_objectives(self, data):

        return True


