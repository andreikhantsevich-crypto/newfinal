from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FinalTrainingType(models.Model):
    _name = "final.training.type"
    _description = "Тип тренировки"
    _order = "sequence, name"

    name = fields.Char(string="Название", required=True)
    code = fields.Selection(
        selection=[
            ("individual", "Индивидуальная"),
            ("split", "Сплит"),
            ("group", "Групповая"),
        ],
        string="Код",
        required=True,
    )
    sequence = fields.Integer(string="Порядок", default=10)
    min_clients = fields.Integer(string="Мин. количество клиентов", required=True)
    max_clients = fields.Integer(string="Макс. количество клиентов", required=True)
    trainer_count = fields.Integer(
        string="Количество тренеров",
        default=1,
        required=True,
    )
    description = fields.Text(string="Описание")
    active = fields.Boolean(default=True, string="Активно")

    _sql_constraints = [
        (
            "final_training_type_code_unique",
            "unique(code)",
            "Код вида тренировки должен быть уникальным.",
        )
    ]

    @api.constrains("min_clients", "max_clients")
    def _check_client_limits(self):
        for record in self:
            if record.min_clients <= 0:
                raise ValidationError("Минимальное количество клиентов должно быть положительным.")
            if record.max_clients < record.min_clients:
                raise ValidationError("Максимальное количество клиентов должно быть не меньше минимального.")



