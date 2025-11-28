# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import timedelta


class FinalTrainingBooking(models.Model):
    _name = "final.training.booking"
    _description = "Запись на тренировку"
    _order = "start_datetime desc"
    _rec_name = "name"

    name = fields.Char(
        string="Описание",
        compute="_compute_name",
        store=True,
        readonly=True,
    )
    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        ondelete="restrict",
        index=True,
    )
    tennis_court_id = fields.Many2one(
        "final.tennis.court",
        string="Теннисный корт",
        required=True,
        ondelete="restrict",
        domain="[('sport_center_id', '=', sport_center_id)]",
        index=True,
    )
    trainer_id = fields.Many2one(
        "hr.employee",
        string="Тренер",
        required=True,
        domain="[('is_final_trainer', '=', True)]",
        index=True,
    )
    training_type_id = fields.Many2one(
        "final.training.type",
        string="Тип тренировки",
        required=True,
        ondelete="restrict",
    )
    client_ids = fields.Many2many(
        "res.partner",
        "final_training_booking_partner_rel",
        "booking_id",
        "partner_id",
        string="Клиенты",
        required=True,
        domain="[('is_company', '=', False)]",
    )
    start_datetime = fields.Datetime(
        string="Дата и время начала",
        required=True,
        index=True,
    )
    end_datetime = fields.Datetime(
        string="Дата и время окончания",
        required=True,
        index=True,
    )
    duration_hours = fields.Float(
        string="Продолжительность (ч.)",
        compute="_compute_duration_hours",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Черновик"),
            ("pending_approval", "На одобрении"),
            ("confirmed", "Подтверждена"),
            ("completed", "Завершена"),
            ("cancelled", "Отменена"),
        ],
        string="Статус",
        default="draft",
        required=True,
        index=True,
    )
    created_by = fields.Many2one(
        "res.users",
        string="Создал",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    approved_by = fields.Many2one(
        "res.users",
        string="Одобрил",
        readonly=True,
        index=True,
    )
    approved_date = fields.Datetime(
        string="Дата одобрения",
        readonly=True,
    )
    total_price = fields.Monetary(
        string="Общая стоимость",
        compute="_compute_total_price",
        store=True,
        currency_field="currency_id",
        readonly=True,
        help="Общая стоимость тренировки (цена за час * продолжительность * количество клиентов)",
    )
    price_per_hour = fields.Monetary(
        string="Цена за час (за чел.)",
        compute="_compute_price_per_hour",
        store=True,
        currency_field="currency_id",
        readonly=True,
        help="Цена за час тренировки данного типа в этом СЦ за человека",
    )
    trainer_rate_per_hour = fields.Monetary(
        string="Ставка тренера за час (за чел.)",
        compute="_compute_trainer_rate_per_hour",
        store=True,
        currency_field="currency_id",
        readonly=True,
        help="Ставка тренера за час тренировки за человека",
    )
    trainer_rate_amount = fields.Monetary(
        string="Ставка тренера",
        compute="_compute_trainer_rate_amount",
        store=True,
        currency_field="currency_id",
        readonly=True,
        help="Общая ставка тренера за тренировку",
    )
    profit_amount = fields.Monetary(
        string="Прибыль",
        compute="_compute_profit_amount",
        store=True,
        currency_field="currency_id",
        readonly=True,
        help="Прибыль = стоимость тренировки - ставка тренера",
    )
    recurring_id = fields.Many2one(
        "final.training.recurring",
        string="Повторяющаяся тренировка",
        ondelete="set null",
        index=True,
    )
    is_recurring = fields.Boolean(
        string="Повторяющаяся",
        default=False,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="sport_center_id.currency_id",
        readonly=True,
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Компания",
        related="sport_center_id.company_id",
        readonly=True,
        store=True,
        index=True,
    )
    telegram_notification_sent = fields.Boolean(
        string="Уведомление отправлено",
        default=False,
        help="Флаг отправки уведомления клиентам через Telegram",
    )
    reminder_sent = fields.Boolean(
        string="Напоминание отправлено",
        default=False,
        help="Флаг отправки напоминания за N часов до начала",
    )
    color = fields.Integer(
        string="Цвет",
        default=0,
        help="Цвет для отображения в календаре",
    )

    _sql_constraints = [
        (
            "final_training_booking_time_check",
            "CHECK(start_datetime < end_datetime)",
            "Дата начала должна предшествовать дате окончания.",
        ),
        (
            "final_training_booking_duration_min",
            "CHECK(duration_hours >= 1)",
            "Минимальная продолжительность тренировки - 1 час.",
        ),
    ]

    @api.depends("trainer_id", "sport_center_id", "training_type_id", "start_datetime", "client_ids")
    def _compute_name(self):
        """Генерация описания тренировки"""
        for record in self:
            if not record.start_datetime:
                record.name = _("Новая тренировка")
                continue
            
            # Форматируем дату и время
            start = fields.Datetime.context_timestamp(record, record.start_datetime)
            date_str = start.strftime("%d.%m.%Y %H:%M")
            
            # Тип тренировки
            type_name = record.training_type_id.name if record.training_type_id else ""
            
            # Тренер
            trainer_name = record.trainer_id.name if record.trainer_id else ""
            
            # Клиенты
            client_count = len(record.client_ids)
            if client_count == 0:
                clients_str = ""
            elif client_count == 1:
                clients_str = record.client_ids[0].name
            elif client_count <= 3:
                clients_str = ", ".join(record.client_ids.mapped("name"))
            else:
                clients_str = f"{record.client_ids[0].name} и еще {client_count - 1}"
            
            name_parts = []
            if type_name:
                name_parts.append(type_name)
            if trainer_name:
                name_parts.append(f"({trainer_name})")
            if clients_str:
                name_parts.append(f"- {clients_str}")
            if date_str:
                name_parts.append(f"({date_str})")
            
            record.name = " ".join(name_parts) if name_parts else _("Тренировка")

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration_hours(self):
        """Расчет продолжительности в часах"""
        for record in self:
            if record.start_datetime and record.end_datetime:
                delta = record.end_datetime - record.start_datetime
                record.duration_hours = delta.total_seconds() / 3600.0
            else:
                record.duration_hours = 0.0

    @api.depends("training_type_id", "sport_center_id")
    def _compute_price_per_hour(self):
        """Получение цены за час из final.center.training.price"""
        for record in self:
            if not record.training_type_id or not record.sport_center_id:
                record.price_per_hour = 0.0
                continue
            
            price = self.env["final.center.training.price"].search([
                ("center_id", "=", record.sport_center_id.id),
                ("training_type_id", "=", record.training_type_id.id),
            ], limit=1)
            
            record.price_per_hour = price.price_per_hour if price else 0.0

    @api.depends("training_type_id", "trainer_id", "sport_center_id")
    def _compute_trainer_rate_per_hour(self):
        """Получение ставки тренера за час"""
        for record in self:
            if not record.training_type_id or not record.trainer_id or not record.sport_center_id:
                record.trainer_rate_per_hour = 0.0
                continue
            
            # Находим связь тренера с центром
            center_trainer = self.env["final.center.trainer"].search([
                ("sport_center_id", "=", record.sport_center_id.id),
                ("employee_id", "=", record.trainer_id.id),
            ], limit=1)
            
            if not center_trainer:
                record.trainer_rate_per_hour = 0.0
                continue
            
            # Получаем ставку в зависимости от типа тренировки
            training_code = record.training_type_id.code
            if training_code == "individual":
                record.trainer_rate_per_hour = center_trainer.individual_rate
            elif training_code == "split":
                record.trainer_rate_per_hour = center_trainer.split_rate
            elif training_code == "group":
                record.trainer_rate_per_hour = center_trainer.group_rate
            else:
                record.trainer_rate_per_hour = 0.0

    @api.depends("trainer_rate_per_hour", "duration_hours", "client_ids")
    def _compute_trainer_rate_amount(self):
        """Расчет общей ставки тренера (ставка за час * продолжительность * количество клиентов)"""
        for record in self:
            client_count = len(record.client_ids)
            record.trainer_rate_amount = record.trainer_rate_per_hour * record.duration_hours * client_count

    @api.depends("price_per_hour", "duration_hours", "client_ids")
    def _compute_total_price(self):
        """Расчет общей стоимости (цена за час * продолжительность * количество клиентов)"""
        for record in self:
            client_count = len(record.client_ids)
            record.total_price = record.price_per_hour * record.duration_hours * client_count

    @api.depends("total_price", "trainer_rate_amount")
    def _compute_profit_amount(self):
        """Расчет прибыли"""
        for record in self:
            record.profit_amount = record.total_price - record.trainer_rate_amount

    @api.onchange("sport_center_id")
    def _onchange_sport_center_id(self):
        """Обновление домена корта при изменении СЦ"""
        if self.sport_center_id:
            return {
                "domain": {
                    "tennis_court_id": [("sport_center_id", "=", self.sport_center_id.id)],
                    "trainer_id": [
                        ("is_final_trainer", "=", True),
                        ("trainer_center_ids", "in", [self.sport_center_id.id]),
                    ],
                }
            }
        return {"domain": {"tennis_court_id": [], "trainer_id": []}}

    @api.onchange("training_type_id")
    def _onchange_training_type_id(self):
        """Предупреждение при неверном количестве клиентов"""
        if not self.training_type_id:
            return
        
        client_count = len(self.client_ids)
        min_clients = self.training_type_id.min_clients
        max_clients = self.training_type_id.max_clients
        
        if client_count < min_clients:
            return {
                "warning": {
                    "title": _("Недостаточно клиентов"),
                    "message": _(
                        "Для тренировки типа '%s' требуется минимум %d клиент(ов). "
                        "Текущее количество: %d."
                    ) % (self.training_type_id.name, min_clients, client_count),
                }
            }
        elif client_count > max_clients:
            return {
                "warning": {
                    "title": _("Слишком много клиентов"),
                    "message": _(
                        "Для тренировки типа '%s' допускается максимум %d клиент(ов). "
                        "Текущее количество: %d."
                    ) % (self.training_type_id.name, max_clients, client_count),
                }
            }

    @api.constrains("tennis_court_id", "start_datetime", "end_datetime")
    def _check_court_availability(self):
        """Проверка занятости корта"""
        for record in self:
            if not record.tennis_court_id or not record.start_datetime or not record.end_datetime:
                continue
            
            # Ищем пересечения с другими записями на том же корте
            overlapping = self.search([
                ("tennis_court_id", "=", record.tennis_court_id.id),
                ("id", "!=", record.id),
                ("state", "in", ["confirmed", "pending_approval", "draft"]),  # Учитываем только активные
                ("start_datetime", "<", record.end_datetime),
                ("end_datetime", ">", record.start_datetime),
            ], limit=1)
            
            if overlapping:
                raise ValidationError(
                    _(
                        "Корт '%s' уже занят в это время другой тренировкой "
                        "(тренер: %s, время: %s - %s)."
                    ) % (
                        record.tennis_court_id.name,
                        overlapping.trainer_id.name if overlapping.trainer_id else _("Не указан"),
                        overlapping.start_datetime.strftime("%d.%m.%Y %H:%M") if overlapping.start_datetime else "",
                        overlapping.end_datetime.strftime("%d.%m.%Y %H:%M") if overlapping.end_datetime else "",
                    )
                )

    @api.constrains("tennis_court_id", "start_datetime", "end_datetime")
    def _check_court_work_time(self):
        """Проверка рабочих часов корта (берутся из СЦ)"""
        for record in self:
            if not record.tennis_court_id or not record.sport_center_id or not record.start_datetime or not record.end_datetime:
                continue
            
            center = record.sport_center_id
            start_local = fields.Datetime.context_timestamp(record, record.start_datetime)
            end_local = fields.Datetime.context_timestamp(record, record.end_datetime)
            
            start_hour = start_local.hour + start_local.minute / 60.0
            end_hour = end_local.hour + end_local.minute / 60.0
            
            if start_hour < center.work_time_start or end_hour > center.work_time_end:
                raise ValidationError(
                    _(
                        "Тренировка должна быть в рабочие часы центра '%s' "
                        "(с %.1f до %.1f часов)."
                    ) % (center.name, center.work_time_start, center.work_time_end)
                )

    @api.constrains("training_type_id", "client_ids")
    def _check_client_count(self):
        """Проверка количества клиентов согласно типу тренировки"""
        for record in self:
            if not record.training_type_id:
                continue
            
            client_count = len(record.client_ids)
            min_clients = record.training_type_id.min_clients
            max_clients = record.training_type_id.max_clients
            
            if client_count < min_clients:
                raise ValidationError(
                    _(
                        "Для тренировки типа '%s' требуется минимум %d клиент(ов). "
                        "Текущее количество: %d."
                    ) % (record.training_type_id.name, min_clients, client_count)
                )
            
            if client_count > max_clients:
                raise ValidationError(
                    _(
                        "Для тренировки типа '%s' допускается максимум %d клиент(ов). "
                        "Текущее количество: %d."
                    ) % (record.training_type_id.name, max_clients, client_count)
                )

    @api.constrains("duration_hours")
    def _check_duration_step(self):
        """Проверка что продолжительность кратна 1 часу"""
        for record in self:
            if record.duration_hours > 0:
                # Проверяем что duration_hours - целое число (с небольшой погрешностью)
                if abs(record.duration_hours - round(record.duration_hours)) > 0.01:
                    raise ValidationError(
                        _("Продолжительность тренировки должна быть кратной 1 часу (1, 2, 3... часов).")
                    )

    @api.constrains("trainer_id", "sport_center_id")
    def _check_trainer_in_center(self):
        """Проверка что тренер привязан к выбранному СЦ"""
        for record in self:
            if record.trainer_id and record.sport_center_id:
                if record.sport_center_id not in record.trainer_id.trainer_center_ids:
                    raise ValidationError(
                        _(
                            "Тренер '%s' не привязан к спортивному центру '%s'. "
                            "Сначала привяжите тренера к центру."
                        ) % (record.trainer_id.name, record.sport_center_id.name)
                    )

    def action_confirm(self):
        """Подтверждение тренировки"""
        self.write({"state": "confirmed"})
        return True

    def action_approve(self):
        """Одобрение тренировки менеджером"""
        self.write({
            "state": "confirmed",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })
        return True

    def action_complete(self):
        """Завершение тренировки (списание баланса)"""
        # Списание баланса будет реализовано в следующем этапе (баланс клиента)
        self.write({"state": "completed"})
        return True

    def action_cancel(self):
        """Отмена тренировки"""
        self.write({"state": "cancelled"})
        return True

    def action_set_draft(self):
        """Возврат в черновик"""
        self.write({
            "state": "draft",
            "approved_by": False,
            "approved_date": False,
        })
        return True

