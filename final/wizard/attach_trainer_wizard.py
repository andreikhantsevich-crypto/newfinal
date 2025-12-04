from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AttachTrainerWizard(models.TransientModel):
    _name = "final.attach.trainer.wizard"
    _description = "Мастер привязки тренера к спортивному центру"
    center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        domain="[('id', 'not in', already_attached_center_ids)]",
    )
    already_attached_center_ids = fields.Many2many(
        "final.sport.center",
        string="Уже привязанные центры",
        compute="_compute_already_attached_centers",
        store=False,
    )
    individual_rate = fields.Monetary(
        string="Ставка за индивидуальную тренировку",
        currency_field="currency_id",
        required=True,
        help="Ставка тренера за час индивидуальной тренировки",
    )
    split_rate = fields.Monetary(
        string="Ставка за сплит тренировку",
        currency_field="currency_id",
        required=True,
        help="Ставка тренера за час сплит тренировки",
    )
    group_rate = fields.Monetary(
        string="Ставка за групповую тренировку",
        currency_field="currency_id",
        required=True,
        help="Ставка тренера за час групповой тренировки",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="center_id.currency_id",
        readonly=True,
    )

    @api.depends("center_id")
    def _compute_already_attached_centers(self):
        for record in self:
            trainer_employee = self.env.user.employee_id
            if trainer_employee:
                record.already_attached_center_ids = trainer_employee.trainer_center_ids
            else:
                record.already_attached_center_ids = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        trainer_employee = self.env.user.employee_id
        if not trainer_employee:
            raise ValidationError(
                _("Текущий пользователь не связан с сотрудником-тренером.")
            )
        if not trainer_employee.is_final_trainer:
            raise ValidationError(
                _("Текущий сотрудник не является тренером.")
            )
        # Устанавливаем центр из контекста, если он передан
        if 'default_center_id' in self.env.context:
            res['center_id'] = self.env.context['default_center_id']
        # Вычисляем уже привязанные центры
        if 'already_attached_center_ids' in fields_list:
            if trainer_employee:
                res['already_attached_center_ids'] = [(6, 0, trainer_employee.trainer_center_ids.ids)]
            else:
                res['already_attached_center_ids'] = [(5, 0, 0)]
        return res

    def action_attach_trainer(self):
        self.ensure_one()
        trainer_employee = self.env.user.employee_id
        
        if not trainer_employee:
            raise ValidationError(
                _("Текущий пользователь не связан с сотрудником-тренером.")
            )

        # Проверяем, не привязан ли уже тренер к этому центру
        existing_link = self.env["final.center.trainer"].search([
            ("employee_id", "=", trainer_employee.id),
            ("sport_center_id", "=", self.center_id.id),
        ], limit=1)
        
        if existing_link:
            raise ValidationError(
                _("Вы уже привязаны к спортивному центру '%s'.") % self.center_id.name
            )

        # Создаем привязку тренера к СЦ
        center_trainer = self.env["final.center.trainer"].create({
            "employee_id": trainer_employee.id,
            "sport_center_id": self.center_id.id,
        })

        # Получаем виды тренировок
        TrainingType = self.env["final.training.type"]
        individual_type = TrainingType.search([("code", "=", "individual")], limit=1)
        split_type = TrainingType.search([("code", "=", "split")], limit=1)
        group_type = TrainingType.search([("code", "=", "group")], limit=1)

        # Создаем ставки для каждого вида тренировки
        TrainerRate = self.env["final.trainer.rate"]
        
        if individual_type and self.individual_rate > 0:
            TrainerRate.create({
                "trainer_id": trainer_employee.id,
                "center_id": self.center_id.id,
                "training_type_id": individual_type.id,
                "hour_rate": self.individual_rate,
            })
        
        if split_type and self.split_rate > 0:
            TrainerRate.create({
                "trainer_id": trainer_employee.id,
                "center_id": self.center_id.id,
                "training_type_id": split_type.id,
                "hour_rate": self.split_rate,
            })
        
        if group_type and self.group_rate > 0:
            TrainerRate.create({
                "trainer_id": trainer_employee.id,
                "center_id": self.center_id.id,
                "training_type_id": group_type.id,
                "hour_rate": self.group_rate,
            })

        # Возвращаем действие для обновления списка
        return {
            "type": "ir.actions.act_window_close",
        }

