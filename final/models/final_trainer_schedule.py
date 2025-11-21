from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FinalTrainerSchedule(models.Model):
    _name = "final.trainer.schedule"
    _description = "Рабочее расписание тренера"
    _order = "start_datetime desc"

    name = fields.Char(
        string="Описание",
        compute="_compute_name",
        store=True,
    )
    trainer_id = fields.Many2one(
        "hr.employee",
        string="Тренер",
        required=True,
        domain="[('is_final_trainer', '=', True)]",
        index=True,
    )
    center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        index=True,
    )
    start_datetime = fields.Datetime(
        string="Начало",
        required=True,
        index=True,
    )
    end_datetime = fields.Datetime(
        string="Окончание",
        required=True,
        index=True,
    )
    duration_hours = fields.Float(
        string="Продолжительность (ч.)",
        compute="_compute_duration_hours",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Компания",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    color = fields.Integer(
        string="Цвет",
        default=0,
        help="Индивидуальный цвет записи в календаре.",
    )

    _sql_constraints = [
        (
            "final_trainer_schedule_time_check",
            "CHECK(start_datetime < end_datetime)",
            "Дата начала должна предшествовать дате окончания.",
        )
    ]

    @api.depends("trainer_id", "center_id", "start_datetime", "end_datetime")
    def _compute_name(self):
        for record in self:
            if record.start_datetime and record.end_datetime:
                name = "%s — %s" % (
                    fields.Datetime.to_string(record.start_datetime),
                    fields.Datetime.to_string(record.end_datetime),
                )
            else:
                name = record.center_id.display_name or _("Рабочий слот")
            if record.center_id:
                name = "%s (%s)" % (record.center_id.display_name, name)
            record.name = name

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration_hours(self):
        for record in self:
            if record.start_datetime and record.end_datetime:
                delta = record.end_datetime - record.start_datetime
                record.duration_hours = delta.total_seconds() / 3600.0
            else:
                record.duration_hours = 0.0

    @api.onchange("trainer_id")
    def _onchange_trainer_id(self):
        if self.trainer_id and self.trainer_id.trainer_center_ids:
            return {
                "domain": {
                    "center_id": [
                        ("id", "in", self.trainer_id.trainer_center_ids.ids),
                    ]
                }
            }
        return {"domain": {"center_id": []}}

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

    @api.constrains("start_datetime", "end_datetime")
    def _check_same_day(self):
        for record in self:
            if not record.start_datetime or not record.end_datetime:
                continue
            start = fields.Datetime.context_timestamp(record, record.start_datetime)
            end = fields.Datetime.context_timestamp(record, record.end_datetime)
            if start.date() != end.date():
                raise ValidationError(
                    _("Рабочий слот должен укладываться в один календарный день.")
                )

    @api.constrains("start_datetime", "end_datetime", "center_id")
    def _check_center_work_time(self):
        for record in self:
            if not record.center_id or not record.start_datetime or not record.end_datetime:
                continue
            start_local = fields.Datetime.context_timestamp(record, record.start_datetime)
            end_local = fields.Datetime.context_timestamp(record, record.end_datetime)
            start_hour = start_local.hour + start_local.minute / 60.0
            end_hour = end_local.hour + end_local.minute / 60.0
            center = record.center_id
            if (
                start_hour < center.work_time_start
                or end_hour > center.work_time_end
                or end_hour <= start_hour
            ):
                raise ValidationError(
                    _(
                        "Время работы должно находиться в диапазоне c %(start)s до %(end)s часов центра %(center)s."
                    )
                    % {
                        "start": center.work_time_start,
                        "end": center.work_time_end,
                        "center": center.display_name,
                    }
                )

    @api.constrains("trainer_id", "start_datetime", "end_datetime")
    def _check_overlap(self):
        for record in self:
            if not record.trainer_id or not record.start_datetime or not record.end_datetime:
                continue
            overlap = self.search_count(
                [
                    ("trainer_id", "=", record.trainer_id.id),
                    ("id", "!=", record.id),
                    ("start_datetime", "<", record.end_datetime),
                    ("end_datetime", ">", record.start_datetime),
                ]
            )
            if overlap:
                raise ValidationError(
                    _(
                        "Рабочие слоты тренера %(trainer)s пересекаются по времени. "
                        "Проверьте расписание."
                    )
                    % {"trainer": record.trainer_id.display_name}
                )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'trainer_id' in fields_list and self.env.user.employee_id:
            res['trainer_id'] = self.env.user.employee_id.id
        return res


