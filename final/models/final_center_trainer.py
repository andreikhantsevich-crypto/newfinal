from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FinalCenterTrainer(models.Model):
    _name = "final.center.trainer"
    _description = "Привязка тренера к спортивному центру"
    _rec_name = "employee_id"

    _sql_constraints = [
        (
            "final_center_trainer_employee_unique",
            "unique(employee_id, sport_center_id)",
            "Сотрудник уже прикреплён к этому спортивному центру.",
        )
    ]

    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Тренер",
        required=True,
        domain="[('is_final_manager', '=', False)]",
    )
    
    # Computed поля для ставок тренера
    individual_rate = fields.Monetary(
        string="Ставка за индивидуальную тренировку",
        compute="_compute_trainer_rates",
        currency_field="currency_id",
        help="Ставка тренера за час индивидуальной тренировки",
    )
    split_rate = fields.Monetary(
        string="Ставка за сплит тренировку",
        compute="_compute_trainer_rates",
        currency_field="currency_id",
        help="Ставка тренера за час сплит тренировки",
    )
    group_rate = fields.Monetary(
        string="Ставка за групповую тренировку",
        compute="_compute_trainer_rates",
        currency_field="currency_id",
        help="Ставка тренера за час групповой тренировки",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="sport_center_id.currency_id",
        readonly=True,
    )

    @api.constrains("employee_id", "sport_center_id")
    def _check_not_manager(self):
        for record in self:
            employee = record.employee_id
            if employee and employee == record.sport_center_id.manager_id:
                raise ValidationError(
                    "Сотрудник уже назначен менеджером этого спортивного центра и не может быть тренером."
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_employee_center()
        return records

    def write(self, vals):
        previous_links = [
            (record.employee_id, record.sport_center_id) for record in self
        ]
        res = super().write(vals)
        self._sync_employee_center()
        self._cleanup_old_links(previous_links)
        return res

    def unlink(self):
        links = [(record.employee_id, record.sport_center_id) for record in self]
        res = super().unlink()
        self._cleanup_old_links(links)
        return res

    def _sync_employee_center(self):
        for record in self:
            employee = record.employee_id
            if not employee:
                continue
            if not employee.is_final_trainer:
                employee.write({"is_final_trainer": True})

    def _cleanup_old_links(self, links):
        for employee, center in links:
            if not employee:
                continue
            has_other_links = self.search_count(
                [
                    ("employee_id", "=", employee.id),
                    ("sport_center_id", "!=", center.id),
                ]
            )
            current_link = self.search_count(
                [
                    ("employee_id", "=", employee.id),
                    ("sport_center_id", "=", center.id),
                ]
            )
            if current_link:
                continue
            if has_other_links:
                continue
            employee.write({"is_final_trainer": False})

    @api.depends("employee_id", "sport_center_id")
    def _compute_trainer_rates(self):
        """Вычисляет ставки тренера за каждый вид тренировки"""
        # Используем sudo для доступа к ставкам тренера
        TrainerRate = self.env["final.trainer.rate"].sudo()
        TrainingType = self.env["final.training.type"]
        
        for record in self:
            record.individual_rate = 0.0
            record.split_rate = 0.0
            record.group_rate = 0.0
            
            if not record.employee_id or not record.sport_center_id:
                continue
            
            # Получаем виды тренировок
            individual_type = TrainingType.search([("code", "=", "individual")], limit=1)
            split_type = TrainingType.search([("code", "=", "split")], limit=1)
            group_type = TrainingType.search([("code", "=", "group")], limit=1)
            
            # Получаем ставки тренера для этого центра
            for code, rate_field, training_type in [
                ("individual", "individual_rate", individual_type),
                ("split", "split_rate", split_type),
                ("group", "group_rate", group_type),
            ]:
                if not training_type:
                    continue
                rate = TrainerRate.search([
                    ("trainer_id", "=", record.employee_id.id),
                    ("center_id", "=", record.sport_center_id.id),
                    ("training_type_id", "=", training_type.id),
                ], limit=1)
                if rate:
                    setattr(record, rate_field, rate.hour_rate)

