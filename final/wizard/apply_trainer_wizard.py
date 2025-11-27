# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ApplyTrainerWizard(models.TransientModel):
    _name = "final.apply.trainer.wizard"
    _description = "Мастер устройства тренера в спортивный центр"

    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        readonly=True,
    )
    
    # Ставки за каждый вид тренировки
    individual_rate = fields.Monetary(
        string="Ставка за индивидуальную тренировку (за чел.)",
        currency_field="currency_id",
        required=True,
    )
    split_rate = fields.Monetary(
        string="Ставка за сплит тренировку (за чел.)",
        currency_field="currency_id",
        required=True,
    )
    group_rate = fields.Monetary(
        string="Ставка за групповую тренировку (за чел.)",
        currency_field="currency_id",
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="sport_center_id.currency_id",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        """Устанавливает значения по умолчанию"""
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
        
        # Устанавливаем центр из контекста
        if 'default_sport_center_id' in self.env.context:
            res['sport_center_id'] = self.env.context['default_sport_center_id']
        elif 'active_id' in self.env.context and self.env.context.get('active_model') == 'final.sport.center':
            res['sport_center_id'] = self.env.context['active_id']
        
        return res

    def action_apply_trainer(self):
        """Привязывает тренера к СЦ и создает ставки"""
        self.ensure_one()
        trainer_employee = self.env.user.employee_id
        
        if not trainer_employee:
            raise ValidationError(
                _("Текущий пользователь не связан с сотрудником-тренером.")
            )

        # Проверяем, не привязан ли уже тренер к этому центру
        existing_link = self.env["final.center.trainer"].search([
            ("employee_id", "=", trainer_employee.id),
            ("sport_center_id", "=", self.sport_center_id.id),
        ], limit=1)
        
        if existing_link:
            raise ValidationError(
                _("Вы уже привязаны к спортивному центру '%s'.") % self.sport_center_id.name
            )

        # Проверяем ставки
        if not self.individual_rate or not self.split_rate or not self.group_rate:
            raise ValidationError(
                _("Необходимо указать ставки за все виды тренировок.")
            )
        
        if self.individual_rate <= 0 or self.split_rate <= 0 or self.group_rate <= 0:
            raise ValidationError(
                _("Ставки должны быть больше нуля.")
            )
        
        # Проверяем ограничения по ставкам (процент от стоимости тренировки)
        center = self.sport_center_id
        
        # Индивидуальная: максимум 40%
        max_individual = round(center.individual_price * 0.40, 2) if center.individual_price else 0
        # Сплит: максимум 35%
        max_split = round(center.split_price * 0.35, 2) if center.split_price else 0
        # Групповая: максимум 30%
        max_group = round(center.group_price * 0.30, 2) if center.group_price else 0
        
        # Проверяем, какая именно ставка превышает лимит
        exceeded_rates = []
        if round(self.individual_rate, 2) > max_individual:
            exceeded_rates.append(_("индивидуальную тренировку"))
        if round(self.split_rate, 2) > max_split:
            exceeded_rates.append(_("сплит тренировку"))
        if round(self.group_rate, 2) > max_group:
            exceeded_rates.append(_("групповую тренировку"))
        
        # Если есть превышения, показываем уведомление
        if exceeded_rates:
            if len(exceeded_rates) == 1:
                message = _("Мы не можем согласиться на ваши условия. Ваша ставка за %s велика.") % exceeded_rates[0]
            elif len(exceeded_rates) == 2:
                message = _("Мы не можем согласиться на ваши условия. Ваши ставки за %s и %s велики.") % (exceeded_rates[0], exceeded_rates[1])
            else:
                message = _("Мы не можем согласиться на ваши условия. Ваши ставки за %s, %s и %s велики.") % (exceeded_rates[0], exceeded_rates[1], exceeded_rates[2])
            
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Отказ"),
                    "message": message,
                    "type": "warning",
                    "sticky": False,
                }
            }

        # Создаем привязку тренера к СЦ с sudo() для обхода прав доступа
        center_trainer = self.env["final.center.trainer"].sudo().create({
            "employee_id": trainer_employee.id,
            "sport_center_id": self.sport_center_id.id,
        })

        # Получаем виды тренировок
        TrainingType = self.env["final.training.type"]
        individual_type = TrainingType.search([("code", "=", "individual")], limit=1)
        split_type = TrainingType.search([("code", "=", "split")], limit=1)
        group_type = TrainingType.search([("code", "=", "group")], limit=1)

        # Создаем ставки для каждого вида тренировки с sudo()
        TrainerRate = self.env["final.trainer.rate"].sudo()
        
        if individual_type and self.individual_rate > 0:
            TrainerRate.create({
                "trainer_id": trainer_employee.id,
                "center_id": self.sport_center_id.id,
                "training_type_id": individual_type.id,
                "hour_rate": self.individual_rate,
            })
        
        if split_type and self.split_rate > 0:
            TrainerRate.create({
                "trainer_id": trainer_employee.id,
                "center_id": self.sport_center_id.id,
                "training_type_id": split_type.id,
                "hour_rate": self.split_rate,
            })
        
        if group_type and self.group_rate > 0:
            TrainerRate.create({
                "trainer_id": trainer_employee.id,
                "center_id": self.sport_center_id.id,
                "training_type_id": group_type.id,
                "hour_rate": self.group_rate,
            })

        # Обновляем зависимости с sudo()
        trainer_employee.sudo()._compute_trainer_center_ids()
        self.sport_center_id.sudo()._compute_is_trainer_attached()
        
        # Возвращаем действие для закрытия wizard
        # Уведомление будет показано через обновление формы СЦ
        return {
            "type": "ir.actions.act_window_close",
        }

