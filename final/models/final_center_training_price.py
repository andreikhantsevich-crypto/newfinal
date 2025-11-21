# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FinalCenterTrainingPrice(models.Model):
    _name = "final.center.training.price"
    _description = "Цена тренировки в спортивном центре"
    _order = "center_id, training_type_id"

    center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        ondelete="cascade",
        index=True,
    )
    training_type_id = fields.Many2one(
        "final.training.type",
        string="Вид тренировки",
        required=True,
        ondelete="cascade",
        index=True,
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
    price_per_hour = fields.Monetary(
        string="Цена за час",
        default=0.0,
        currency_field="currency_id",
        help="Стоимость одного часа тренировки данного типа в этом спортивном центре для клиента.",
    )

    _sql_constraints = [
        (
            "final_center_training_price_unique",
            "unique(center_id, training_type_id)",
            "Цена для этого центра и вида тренировки уже задана.",
        )
    ]

    @api.constrains("price_per_hour")
    def _check_price_not_negative(self):
        for record in self:
            if record.price_per_hour < 0:
                raise ValidationError(_("Цена за час не может быть отрицательной."))

