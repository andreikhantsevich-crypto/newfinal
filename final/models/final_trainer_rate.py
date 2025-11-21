from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FinalTrainerRate(models.Model):
    _name = "final.trainer.rate"
    _description = "Ставка тренера за час"
    _order = "trainer_id, center_id, training_type_id"

    trainer_id = fields.Many2one(
        "hr.employee",
        string="Тренер",
        required=True,
        domain="[('is_final_trainer', '=', True)]",
    )
    center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
    )
    training_type_id = fields.Many2one(
        "final.training.type",
        string="Вид тренировки",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Компания",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )
    hour_rate = fields.Monetary(
        string="Ставка за час",
        required=True,
        currency_field="currency_id",
        help="Размер выплаты тренеру за один час тренировки данного типа.",
    )

    _sql_constraints = [
        (
            "final_trainer_rate_unique",
            "unique(trainer_id, center_id, training_type_id)",
            "Ставка для этого тренера, центра и типа занятия уже задана.",
        )
    ]

    @api.constrains("trainer_id", "center_id")
    def _check_center_available(self):
        for record in self:
            if (
                record.trainer_id
                and record.center_id
                and record.center_id not in record.trainer_id.trainer_center_ids
            ):
                raise ValidationError(
                    _(
                        "Тренер %(trainer)s не привязан к спортивному центру %(center)s. "
                        "Добавьте связь на вкладке тренеров в карточке центра."
                    )
                    % {
                        "trainer": record.trainer_id.display_name,
                        "center": record.center_id.display_name,
                    }
                )

    @api.constrains("hour_rate")
    def _check_hour_rate_positive(self):
        for record in self:
            if record.hour_rate <= 0:
                raise ValidationError(_("Ставка за час должна быть больше нуля."))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'trainer_id' in fields_list and self.env.user.employee_id:
            res['trainer_id'] = self.env.user.employee_id.id
        return res



