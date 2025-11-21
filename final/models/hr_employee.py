from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
            employee.trainer_center_ids = employee.center_trainer_ids.mapped(
                "sport_center_id"
            )

