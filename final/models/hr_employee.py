import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrEmployeePublic(models.Model):
    """Расширение hr.employee.public для доступа к нашим полям"""
    _inherit = "hr.employee.public"
    
    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        related="employee_id.sport_center_id",
        readonly=True,
        store=False,
    )
    is_final_trainer = fields.Boolean(
        string="Тренер СЦ",
        related="employee_id.is_final_trainer",
        readonly=True,
        store=False,
    )
    is_final_manager = fields.Boolean(
        string="Менеджер СЦ",
        related="employee_id.is_final_manager",
        readonly=True,
        store=False,
    )


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        ondelete="set null",
    )
    is_final_trainer = fields.Boolean(
        string="Тренер СЦ",
        help="Отметьте, если сотрудник является тренером в сети спортивных центров.",
    )
    is_final_manager = fields.Boolean(
        string="Менеджер СЦ",
        help="Отметьте, если сотрудник является менеджером спортивного центра.",
    )
    center_trainer_ids = fields.One2many(
        "final.center.trainer",
        "employee_id",
        string="Назначения тренера",
    )
    trainer_center_ids = fields.Many2many(
        "final.sport.center",
        string="Центры тренера",
        compute="_compute_trainer_center_ids",
        compute_sudo=True,
    )
    trainer_center_count = fields.Integer(
        string="Количество СЦ",
        compute="_compute_trainer_center_ids",
        compute_sudo=True,
    )
    
    # Related поля для личного кабинета тренера
    trainer_login = fields.Char(
        string="Логин",
        related="user_id.login",
        readonly=True,
    )
    trainer_email = fields.Char(
        string="Почта",
        related="work_email",
        readonly=True,
    )

    @api.constrains("sport_center_id")
    def _check_manager_center_consistency(self):
        SportCenter = self.env["final.sport.center"]
        for employee in self:
            manager_center = SportCenter.search([("manager_id", "=", employee.id)], limit=1)
            if manager_center:
                if not employee.sport_center_id:
                    raise ValidationError(
                        "Менеджер должен быть привязан к спортивному центру."
                    )
                if employee.sport_center_id != manager_center:
                    raise ValidationError(
                        "Нельзя назначить менеджера на другой спортивный центр."
                    )

    @api.depends("center_trainer_ids.sport_center_id")
    def _compute_trainer_center_ids(self):
        for employee in self:
            centers = employee.center_trainer_ids.mapped("sport_center_id")
            employee.trainer_center_ids = centers
            employee.trainer_center_count = len(centers)
    
    @api.model
    def action_open_trainer_cabinet(self):
        """Открыть личный кабинет тренера"""
        _logger.info("=== action_open_trainer_cabinet called ===")
        _logger.info("User: %s", self.env.user.name)
        employee = self.env.user.employee_id
        _logger.info("Employee: %s (id=%s)", employee.name if employee else 'None', employee.id if employee else 'None')
        
        if not employee:
            _logger.warning("No employee found for user")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Ошибка',
                    'message': 'Сотрудник не найден для текущего пользователя.',
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        try:
            view_id = self.env.ref('final.view_my_trainer_cabinet_form').id
            _logger.info("View ID: %s", view_id)
        except Exception as e:
            _logger.error("Error getting view: %s", e)
            view_id = False
        
        result = {
            'type': 'ir.actions.act_window',
            'name': 'Личный кабинет',
            'res_model': 'hr.employee',
            'res_id': employee.id,
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
        }
        _logger.info("Returning action: %s", result)
        return result

