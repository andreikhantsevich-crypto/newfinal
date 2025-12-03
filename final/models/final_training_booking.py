# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import requests
import requests


class FinalTrainingBooking(models.Model):
    _name = "final.training.booking"
    _description = "Запись на тренировку"
    _order = "create_date desc, id desc"
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
        # Домен убран, так как валидация происходит в wizard'е и через constraint'ы
        # Домен вызывал проблемы с доступом для тренеров при создании записи
        index=True,
        check_company=False,  # Отключаем проверку компании для обхода правил доступа
    )
    trainer_name = fields.Char(
        string="Имя тренера",
        compute="_compute_trainer_name",
        store=False,
        help="Имя тренера для отображения (используется для обхода правил доступа)",
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
        domain="[('is_company', '=', False), ('telegram_user_id', '!=', False)]",
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
    rejection_reason = fields.Text(
        string="Причина отклонения",
        readonly=True,
        help="Причина отклонения запроса на тренировку",
    )
    rejected_by = fields.Many2one(
        "res.users",
        string="Отклонил",
        readonly=True,
        index=True,
    )
    rejected_date = fields.Datetime(
        string="Дата отклонения",
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
        compute="_compute_color",
        store=True,
        help="Цвет для отображения в календаре (на основе статуса)",
    )
    clients_balance_info = fields.Html(
        string="Информация о балансе клиентов",
        compute="_compute_clients_balance_info",
        store=False,
        help="Информация о балансе клиентов для менеджера",
    )
    # Поля для запроса на отмену
    cancel_requested = fields.Boolean(
        string="Запрос на отмену",
        default=False,
        help="Запрос на отмену тренировки, ожидающий одобрения менеджера",
    )
    cancel_requested_by = fields.Many2one(
        "res.users",
        string="Запросил отмену",
        readonly=True,
        help="Пользователь, который запросил отмену тренировки",
    )
    cancel_requested_date = fields.Datetime(
        string="Дата запроса отмены",
        readonly=True,
    )
    cancel_request_reason = fields.Text(
        string="Причина отмены",
        readonly=True,
        help="Причина запроса на отмену тренировки",
    )
    # Поля для запроса на перенос
    reschedule_requested = fields.Boolean(
        string="Запрос на перенос",
        default=False,
        help="Запрос на перенос тренировки, ожидающий одобрения менеджера",
    )
    reschedule_requested_by = fields.Many2one(
        "res.users",
        string="Запросил перенос",
        readonly=True,
        help="Пользователь, который запросил перенос тренировки",
    )
    reschedule_requested_date = fields.Datetime(
        string="Дата запроса переноса",
        readonly=True,
    )
    reschedule_new_start_datetime = fields.Datetime(
        string="Новое время начала",
        readonly=True,
        help="Новое время начала тренировки (при переносе)",
    )
    reschedule_new_end_datetime = fields.Datetime(
        string="Новое время окончания",
        readonly=True,
        help="Новое время окончания тренировки (при переносе)",
    )
    reschedule_new_court_id = fields.Many2one(
        "final.tennis.court",
        string="Новый корт",
        readonly=True,
        help="Новый корт для тренировки (при переносе, опционально)",
    )
    reschedule_reason = fields.Text(
        string="Причина переноса",
        readonly=True,
        help="Причина запроса на перенос тренировки",
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

    @api.depends("trainer_id")
    def _compute_trainer_name(self):
        """Вычисляет имя тренера с использованием sudo() для обхода правил доступа"""
        for record in self:
            if record.trainer_id:
                # Используем sudo() для чтения имени тренера
                try:
                    trainer_sudo = record.sudo().trainer_id
                    record.trainer_name = trainer_sudo.name if trainer_sudo.exists() else ""
                except Exception:
                    record.trainer_name = ""
            else:
                record.trainer_name = ""
    
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

    @api.depends("state")
    def _compute_color(self):
        """Вычисление цвета для календаря на основе статуса"""
        # Цвета для статусов:
        # 0 - черный (draft)
        # 1 - красный (cancelled)
        # 2 - оранжевый (pending_approval)
        # 3 - желтый (confirmed)
        # 4 - зеленый (completed)
        color_map = {
            "draft": 0,
            "cancelled": 1,
            "pending_approval": 2,
            "confirmed": 3,
            "completed": 4,
        }
        for record in self:
            record.color = color_map.get(record.state, 0)

    @api.depends("client_ids", "price_per_hour", "duration_hours", "state")
    def _compute_clients_balance_info(self):
        """Вычисляет информацию о балансе клиентов для отображения менеджеру"""
        for record in self:
            if not record.client_ids or record.state != "pending_approval":
                record.clients_balance_info = ""
                continue
            
            # Рассчитываем сумму списания для каждого клиента
            amount_per_client = record.price_per_hour * record.duration_hours
            
            html_parts = ["<div style='margin: 10px 0;'>"]
            html_parts.append(f"<strong>Сумма списания с каждого клиента: {amount_per_client} {record.currency_id.symbol if record.currency_id else ''}</strong><br/><br/>")
            html_parts.append("<table class='table table-bordered' style='width: 100%;'>")
            html_parts.append("<thead><tr><th>Клиент</th><th>Баланс</th><th>Статус</th></tr></thead>")
            html_parts.append("<tbody>")
            
            all_sufficient = True
            for client in record.client_ids:
                balance = client.balance
                currency_symbol = client.balance_currency_id.symbol if client.balance_currency_id else ""
                is_sufficient = balance >= amount_per_client
                
                if not is_sufficient:
                    all_sufficient = False
                
                status = "✓ Достаточно" if is_sufficient else "✗ Недостаточно"
                status_color = "green" if is_sufficient else "red"
                
                html_parts.append(
                    f"<tr>"
                    f"<td>{client.name}</td>"
                    f"<td>{balance} {currency_symbol}</td>"
                    f"<td style='color: {status_color}; font-weight: bold;'>{status}</td>"
                    f"</tr>"
                )
            
            html_parts.append("</tbody></table>")
            
            if not all_sufficient:
                html_parts.append(
                    "<div class='alert alert-danger' role='alert' style='margin-top: 10px;'>"
                    "<strong>Внимание!</strong> У некоторых клиентов недостаточно средств на балансе. "
                    "Пополните баланс перед одобрением тренировки."
                    "</div>"
                )
            else:
                html_parts.append(
                    "<div class='alert alert-success' role='alert' style='margin-top: 10px;'>"
                    "✓ У всех клиентов достаточно средств на балансе."
                    "</div>"
                )
            
            html_parts.append("</div>")
            record.clients_balance_info = "".join(html_parts)

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

    @api.constrains("trainer_id", "start_datetime", "end_datetime")
    def _check_trainer_availability(self):
        """Проверка занятости тренера (нельзя вести две тренировки одновременно).

        Требование ТЗ (п.12) в трактовке:
        тренер может работать в нескольких СЦ, но не может
        иметь пересекающиеся по времени тренировки (даже в разных СЦ/на разных кортах).
        """
        for record in self:
            if not record.trainer_id or not record.start_datetime or not record.end_datetime:
                continue

            overlapping = self.search([
                ("trainer_id", "=", record.trainer_id.id),
                ("id", "!=", record.id),
                ("state", "in", ["draft", "pending_approval", "confirmed"]),
                ("start_datetime", "<", record.end_datetime),
                ("end_datetime", ">", record.start_datetime),
            ], limit=1)

            if overlapping:
                raise ValidationError(
                    _(
                        "Тренер '%s' уже занят другой тренировкой в это время "
                        "(СЦ: %s, корт: %s, время: %s - %s). "
                        "Тренер не может проводить несколько тренировок одновременно."
                    )
                    % (
                        record.trainer_id.name or _("Не указан"),
                        overlapping.sport_center_id.name or _("Не указан"),
                        overlapping.tennis_court_id.name or _("Не указан"),
                        overlapping.start_datetime.strftime("%d.%m.%Y %H:%M") if overlapping.start_datetime else "",
                        overlapping.end_datetime.strftime("%H:%M") if overlapping.end_datetime else "",
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
                # Используем прямой поиск через final.center.trainer с sudo(), чтобы гарантировать проверку всех СЦ
                center_trainer_record = self.env["final.center.trainer"].sudo().search([
                    ("employee_id", "=", record.trainer_id.id),
                    ("sport_center_id", "=", record.sport_center_id.id),
                ], limit=1)
                if not center_trainer_record:
                    # Используем sudo() для чтения имени тренера, чтобы обойти проблемы с доступом
                    trainer_name = record.trainer_id.sudo().name if record.trainer_id.exists() else _("Неизвестный тренер")
                    raise ValidationError(
                        _(
                            "Тренер '%s' не привязан к спортивному центру '%s'. "
                            "Сначала привяжите тренера к центру."
                        ) % (trainer_name, record.sport_center_id.name)
                    )

    def action_confirm(self):
        """Подтверждение тренировки"""
        self.write({"state": "confirmed"})
        return True

    def action_approve(self):
        """Одобрение тренировки менеджером"""
        self.ensure_one()
        
        # Проверка прав - только менеджер или директор
        if not self.env.user.has_group("final.group_final_manager") and not self.env.user.has_group("final.group_final_director"):
            raise ValidationError(_("Только менеджер или директор могут одобрять тренировки."))
        
        # Проверка что запись в статусе ожидания одобрения
        if self.state != "pending_approval":
            raise ValidationError(_("Можно одобрить только записи со статусом 'На одобрении'."))
        
        # Проверка баланса клиентов перед одобрением
        # Рассчитываем сумму списания для каждого клиента
        amount_per_client = self.price_per_hour * self.duration_hours
        
        if amount_per_client > 0:
            insufficient_balance_clients = []
            for client in self.client_ids:
                if client.balance < amount_per_client:
                    insufficient_balance_clients.append(
                        f"{client.name} (баланс: {client.balance} {client.balance_currency_id.symbol if client.balance_currency_id else ''}, требуется: {amount_per_client} {client.balance_currency_id.symbol if client.balance_currency_id else ''})"
                    )
            
            if insufficient_balance_clients:
                raise ValidationError(
                    _(
                        "Нельзя одобрить тренировку: недостаточно средств на балансе у следующих клиентов:\n%s\n"
                        "Пополните баланс клиентов перед одобрением тренировки."
                    )
                    % "\n".join(insufficient_balance_clients)
                )
        
        self.write({
            "state": "confirmed",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
            "rejection_reason": False,
            "rejected_by": False,
            "rejected_date": False,
        })
        
        # Если это повторяющаяся тренировка, одобряем также шаблон
        if self.is_recurring and self.recurring_id:
            self.recurring_id.write({
                "approved": True,
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            })
        
        # Отправка уведомления тренеру
        self._notify_trainer_approval()

        # Отправка уведомлений клиентам о подтвержденной тренировке
        self._notify_clients_booking_created()
        # Напоминание за час до начала будет отправлено автоматически через cron-задачу
        
        return True
    
    def action_reject(self):
        """Отклонение тренировки менеджером"""
        self.ensure_one()
        
        # Проверка прав - только менеджер или директор
        if not self.env.user.has_group("final.group_final_manager") and not self.env.user.has_group("final.group_final_director"):
            raise ValidationError(_("Только менеджер или директор могут отклонять тренировки."))
        
        # Проверка что запись в статусе ожидания одобрения
        if self.state != "pending_approval":
            raise ValidationError(_("Можно отклонить только записи со статусом 'На одобрении'."))
        
        # Открываем wizard для указания причины отклонения
        return {
            "type": "ir.actions.act_window",
            "name": _("Отклонить тренировку"),
            "res_model": "final.training.booking.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_booking_id": self.id,
            },
        }
    
    def action_reject_confirm(self, rejection_reason=""):
        """Подтверждение отклонения с причиной"""
        self.ensure_one()
        
        self.write({
            "state": "cancelled",
            "rejection_reason": rejection_reason,
            "rejected_by": self.env.user.id,
            "rejected_date": fields.Datetime.now(),
            "approved_by": False,
            "approved_date": False,
        })
        
        # Отправка уведомления тренеру
        self._notify_trainer_rejection()
        
        return True
    
    def _notify_trainer_approval(self):
        """Отправка уведомления тренеру об одобрении"""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id
        if not trainer or not trainer.user_id:
            return
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Тренировка одобрена"),
            "body": _(
                "Ваша тренировка '%s' (%s - %s) была одобрена менеджером."
            ) % (
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
            ),
            "partner_ids": [(4, trainer.user_id.partner_id.id)],
        })
    
    def _notify_trainer_rejection(self):
        """Отправка уведомления тренеру об отклонении"""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id
        if not trainer or not trainer.user_id:
            return
        
        reason_text = f"\n\nПричина: {self.rejection_reason}" if self.rejection_reason else ""
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Тренировка отклонена"),
            "body": _(
                "Ваша тренировка '%s' (%s - %s) была отклонена менеджером.%s"
            ) % (
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
                reason_text,
            ),
            "partner_ids": [(4, trainer.user_id.partner_id.id)],
        })
    
    def _notify_trainer_cancel_approved(self):
        """Отправка уведомления тренеру об одобрении отмены"""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id
        if not trainer or not trainer.user_id:
            return
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Запрос на отмену одобрен"),
            "body": _(
                "Ваш запрос на отмену тренировки '%s' (%s - %s) был одобрен менеджером."
            ) % (
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
            ),
            "partner_ids": [(4, trainer.user_id.partner_id.id)],
        })
    
    def _notify_trainer_cancel_rejected(self, rejection_reason=""):
        """Отправка уведомления тренеру об отклонении отмены"""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id
        if not trainer or not trainer.user_id:
            return
        
        reason_text = f"\n\nПричина: {rejection_reason}" if rejection_reason else ""
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Запрос на отмену отклонен"),
            "body": _(
                "Ваш запрос на отмену тренировки '%s' (%s - %s) был отклонен менеджером.%s"
            ) % (
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
                reason_text,
            ),
            "partner_ids": [(4, trainer.user_id.partner_id.id)],
        })
    
    def _notify_trainer_reschedule_approved(self):
        """Отправка уведомления тренеру об одобрении переноса"""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id
        if not trainer or not trainer.user_id:
            return
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Запрос на перенос одобрен"),
            "body": _(
                "Ваш запрос на перенос тренировки '%s' был одобрен менеджером. "
                "Новое время: %s - %s"
            ) % (
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
            ),
            "partner_ids": [(4, trainer.user_id.partner_id.id)],
        })
    
    def _notify_trainer_reschedule_rejected(self, rejection_reason=""):
        """Отправка уведомления тренеру об отклонении переноса"""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id
        if not trainer or not trainer.user_id:
            return
        
        reason_text = f"\n\nПричина: {rejection_reason}" if rejection_reason else ""
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Запрос на перенос отклонен"),
            "body": _(
                "Ваш запрос на перенос тренировки '%s' (%s - %s) был отклонен менеджером.%s"
            ) % (
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
                reason_text,
            ),
            "partner_ids": [(4, trainer.user_id.partner_id.id)],
        })
    
    def _notify_manager_cancel_request(self):
        """Отправка уведомления менеджеру о запросе на отмену"""
        if not self.sport_center_id or not self.sport_center_id.manager_id or not self.sport_center_id.manager_id.user_id:
            return
        
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer_name = self.sudo().trainer_id.name if self.sudo().trainer_id else _("Не указан")
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Новый запрос на отмену тренировки"),
            "body": _(
                "Тренер %s запросил отмену тренировки '%s' (%s - %s). "
                "Требуется ваше одобрение."
            ) % (
                trainer_name,
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
            ),
            "partner_ids": [(4, self.sport_center_id.manager_id.user_id.partner_id.id)],
        })
    
    def _notify_manager_reschedule_request(self):
        """Отправка уведомления менеджеру о запросе на перенос"""
        if not self.sport_center_id or not self.sport_center_id.manager_id or not self.sport_center_id.manager_id.user_id:
            return
        
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer_name = self.sudo().trainer_id.name if self.sudo().trainer_id else _("Не указан")
        
        new_time_str = ""
        if self.reschedule_new_start_datetime and self.reschedule_new_end_datetime:
            new_time_str = f"Новое время: {self.reschedule_new_start_datetime.strftime('%d.%m.%Y %H:%M')} - {self.reschedule_new_end_datetime.strftime('%H:%M')}"
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Новый запрос на перенос тренировки"),
            "body": _(
                "Тренер %s запросил перенос тренировки '%s' (%s - %s). "
                "%s "
                "Требуется ваше одобрение."
            ) % (
                trainer_name,
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
                new_time_str,
            ),
            "partner_ids": [(4, self.sport_center_id.manager_id.user_id.partner_id.id)],
        })
    
    def _notify_clients_booking_cancelled(self):
        """Отправка уведомлений клиентам об отмене тренировки"""
        self.ensure_one()
        
        if not self.client_ids:
            return
        
        # Формируем сообщение об отмене
        if self.start_datetime:
            date_str = self.start_datetime.strftime("%d.%m.%Y")
            time_start = self.start_datetime.strftime("%H:%M")
        else:
            date_str = ""
            time_start = ""
        
        if self.end_datetime:
            time_end = self.end_datetime.strftime("%H:%M")
        else:
            time_end = ""
        
        center = self.sport_center_id.name or ""
        court = self.tennis_court_id.name or ""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id.name if self.sudo().trainer_id else ""
        
        message_text = "\n".join([
            "❌ <b>Тренировка отменена</b>",
            "",
            f"📅 {date_str} {time_start}–{time_end}",
            f"🏟 {center} — {court}" if center or court else "",
            f"👨‍🏫 Тренер: {trainer}" if trainer else "",
        ])
        
        for partner in self.client_ids:
            self._send_telegram_message(partner, message_text)
    
    def _notify_clients_booking_rescheduled(self, old_start, old_end, old_court):
        """Отправка уведомлений клиентам о переносе тренировки"""
        self.ensure_one()
        
        if not self.client_ids:
            return
        
        # Формируем сообщение о переносе
        old_date_str = old_start.strftime("%d.%m.%Y") if old_start else ""
        old_time_start = old_start.strftime("%H:%M") if old_start else ""
        old_time_end = old_end.strftime("%H:%M") if old_end else ""
        
        new_date_str = self.start_datetime.strftime("%d.%m.%Y") if self.start_datetime else ""
        new_time_start = self.start_datetime.strftime("%H:%M") if self.start_datetime else ""
        new_time_end = self.end_datetime.strftime("%H:%M") if self.end_datetime else ""
        
        center = self.sport_center_id.name or ""
        court = self.tennis_court_id.name or ""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id.name if self.sudo().trainer_id else ""
        
        message_text = "\n".join([
            "🔄 <b>Тренировка перенесена</b>",
            "",
            f"Старое время: {old_date_str} {old_time_start}–{old_time_end}",
            f"Новое время: {new_date_str} {new_time_start}–{new_time_end}",
            f"🏟 {center} — {court}" if center or court else "",
            f"👨‍🏫 Тренер: {trainer}" if trainer else "",
        ])
        
        for partner in self.client_ids:
            self._send_telegram_message(partner, message_text)

    # === Telegram-уведомления клиентам ===

    def _get_telegram_bot_token(self):
        """Получить токен Telegram-бота из настроек системы."""
        param_env = self.env["ir.config_parameter"].sudo()
        return param_env.get_param("final.telegram_bot_token") or ""

    def _send_telegram_message(self, partner, text):
        """Отправка сообщения клиенту в Telegram напрямую через Bot API.

        Использует:
        - final.telegram_bot_token — токен бота
        - partner.telegram_user_id — chat_id
        """
        if not partner or not partner.telegram_user_id:
            return

        bot_token = self._get_telegram_bot_token()
        if not bot_token:
            # Токен не настроен — тихо выходим, чтобы не ломать поток бизнес-логики
            return

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": partner.telegram_user_id,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            # Используем небольшой таймаут, чтобы не блокировать воркер надолго
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            # Логируем успешную отправку
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(
                "Telegram уведомление отправлено клиенту %s (ID: %s)",
                partner.name, partner.telegram_user_id
            )
        except Exception as e:
            # Логируем ошибку, но не поднимаем исключение — уведомления не должны ломать основной поток
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(
                "Ошибка отправки Telegram уведомления клиенту %s (ID: %s): %s",
                partner.name if partner else "Unknown",
                partner.telegram_user_id if partner else "Unknown",
                str(e)
            )
            return

    def _build_booking_message(self, is_reminder=False):
        """Собирает текст сообщения о тренировке для клиента."""
        self.ensure_one()

        # Используем время напрямую из полей без конвертации часового пояса,
        # чтобы избежать сдвига времени в сообщениях
        if self.start_datetime:
            date_str = self.start_datetime.strftime("%d.%m.%Y")
            time_start = self.start_datetime.strftime("%H:%M")
        else:
            date_str = ""
            time_start = ""
        
        if self.end_datetime:
            time_end = self.end_datetime.strftime("%H:%M")
        else:
            time_end = ""

        center = self.sport_center_id.name or ""
        court = self.tennis_court_id.name or ""
        # Используем sudo() для чтения trainer_id, чтобы обойти правила доступа
        trainer = self.sudo().trainer_id.name if self.sudo().trainer_id else ""
        training_type = self.training_type_id.name or ""

        if is_reminder:
            header = "Напоминание о тренировке через 1 час:"
        else:
            header = "Вы записаны на тренировку:"

        lines = [
            header,
            "",
            f"📅 <b>{date_str}</b> {time_start}–{time_end}",
            f"🏟 {center} — {court}" if center or court else "",
            f"👨‍🏫 Тренер: {trainer}" if trainer else "",
            f"Тип: {training_type}" if training_type else "",
        ]

        # Убираем пустые строки
        lines = [l for l in lines if l]
        return "\n".join(lines)

    def _notify_clients_booking_created(self):
        """Отправка уведомлений клиентам при подтверждении тренировки.

        Отправляется:
        - при создании подтвержденной тренировки менеджером
        - при одобрении тренировки менеджером (после pending_approval)
        """
        self.ensure_one()

        # Не уведомляем повторно, если уже отправляли
        if self.telegram_notification_sent:
            return

        # Уведомляем только для подтвержденных тренировок
        if self.state != "confirmed":
            return

        message_text = self._build_booking_message(is_reminder=False)
        for partner in self.client_ids:
            self._send_telegram_message(partner, message_text)

        # Помечаем, что уведомление отправлено
        self.telegram_notification_sent = True

    def _maybe_send_reminder_immediately(self):
        """Отправить напоминание сразу, если до тренировки осталось <= N часов.

        Это защищает от ситуации, когда cron ещё не успел отработать,
        а тренировка уже скоро начнётся.
        """
        self.ensure_one()

        # Напоминания отправляем только для подтверждённых тренировок
        if self.state != "confirmed" or self.reminder_sent:
            return

        if not self.start_datetime:
            return

        param_env = self.env["ir.config_parameter"].sudo()
        try:
            hours_str = param_env.get_param("final.reminder_hours") or "1"
            reminder_hours = float(hours_str)
        except Exception:
            reminder_hours = 1.0

        now = fields.Datetime.now()
        # Если тренировка уже началась или закончилась — напоминание не шлём
        if self.start_datetime <= now:
            return

        delta_hours = (self.start_datetime - now).total_seconds() / 3600.0
        if 0 < delta_hours <= reminder_hours:
            message_text = self._build_booking_message(is_reminder=True)
            for partner in self.client_ids:
                self._send_telegram_message(partner, message_text)
            self.reminder_sent = True

    @api.model
    def cron_send_training_reminders(self):
        """Cron-задача: отправка напоминаний клиентам за 1 час до тренировки.

        Логика:
        - Берём тренировки в статусе confirmed
        - У которых reminder_sent = False
        - Время начала в интервале [now, now + N часов]
          (N берётся из настроек final.reminder_hours, по умолчанию 1)
        - Для каждого клиента отправляем сообщение и отмечаем reminder_sent = True
        """
        param_env = self.env["ir.config_parameter"].sudo()
        try:
            hours_str = param_env.get_param("final.reminder_hours") or "1"
            reminder_hours = float(hours_str)
        except Exception:
            reminder_hours = 1.0

        now = fields.Datetime.now()
        # Вычисляем временной интервал для отправки напоминаний:
        # от (reminder_hours - 0.2) до (reminder_hours + 0.2) часов до начала
        # Это позволяет учесть погрешность времени выполнения cron (запускается каждые 10 минут)
        reminder_min = now + timedelta(hours=reminder_hours - 0.2)
        reminder_max = now + timedelta(hours=reminder_hours + 0.2)

        # Берём все неподтверждённые напоминания для тренировок,
        # которые начнутся в интервале [reminder_min, reminder_max] (примерно за N часов).
        bookings = self.sudo().search([
            ("state", "=", "confirmed"),
            ("reminder_sent", "=", False),
            ("start_datetime", ">=", reminder_min),
            ("start_datetime", "<=", reminder_max),
        ])

        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(
            "Cron напоминаний: найдено %d тренировок для отправки напоминаний",
            len(bookings)
        )
        
        for booking in bookings:
            message_text = booking._build_booking_message(is_reminder=True)
            _logger.info(
                "Отправка напоминания о тренировке ID=%d клиентам: %s",
                booking.id,
                ", ".join(booking.client_ids.mapped("name"))
            )
            for partner in booking.client_ids:
                booking._send_telegram_message(partner, message_text)
            booking.reminder_sent = True

    @api.model
    def cron_auto_complete_trainings(self):
        """Cron-задача: автоматическое завершение тренировок после окончания времени.

        Логика:
        - Берём тренировки в статусе confirmed
        - У которых end_datetime < now (время окончания уже прошло)
        - Автоматически завершаем их (списываем баланс)
        - Если баланса недостаточно, логируем предупреждение и оставляем в статусе confirmed
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        now = fields.Datetime.now()
        
        # Ищем тренировки, которые уже закончились, но ещё не завершены
        bookings = self.sudo().search([
            ("state", "=", "confirmed"),
            ("end_datetime", "<", now),
        ])
        
        _logger.info(
            "Cron автоматического завершения: найдено %d тренировок для завершения",
            len(bookings)
        )
        
        for booking in bookings:
            try:
                # Рассчитываем сумму списания для каждого клиента
                amount_per_client = booking.price_per_hour * booking.duration_hours
                
                # Проверяем баланс всех клиентов
                insufficient_balance_clients = []
                for client in booking.client_ids:
                    if client.balance < amount_per_client:
                        insufficient_balance_clients.append(
                            f"{client.name} (баланс: {client.balance} {client.balance_currency_id.symbol if client.balance_currency_id else ''}, требуется: {amount_per_client} {client.balance_currency_id.symbol if client.balance_currency_id else ''})"
                        )
                
                if insufficient_balance_clients:
                    # Если баланса недостаточно, логируем предупреждение и не завершаем
                    _logger.warning(
                        "Не удалось автоматически завершить тренировку ID=%d: недостаточно средств на балансе у клиентов: %s",
                        booking.id,
                        ", ".join(insufficient_balance_clients)
                    )
                    continue
                
                # Списываем средства с баланса всех клиентов
                transaction_model = self.env["final.balance.transaction"]
                for client in booking.client_ids:
                    description = _(
                        "Списание за тренировку '%s' (%s - %s)"
                    ) % (
                        booking.name or _("Тренировка"),
                        booking.start_datetime.strftime("%d.%m.%Y %H:%M") if booking.start_datetime else "",
                        booking.end_datetime.strftime("%H:%M") if booking.end_datetime else "",
                    )
                    
                    try:
                        transaction_model.action_withdrawal(
                            client.id,
                            amount_per_client,
                            booking.id,
                            description,
                        )
                    except ValidationError as e:
                        _logger.error(
                            "Ошибка при автоматическом списании средств с баланса клиента '%s' для тренировки ID=%d: %s",
                            client.name,
                            booking.id,
                            str(e)
                        )
                        # Если ошибка при списании, не завершаем тренировку
                        break
                else:
                    # Если все списания прошли успешно, завершаем тренировку
                    booking.write({"state": "completed"})
                    _logger.info(
                        "Тренировка ID=%d автоматически завершена, средства списаны с балансов клиентов",
                        booking.id
                    )
                    
            except Exception as e:
                _logger.error(
                    "Ошибка при автоматическом завершении тренировки ID=%d: %s",
                    booking.id,
                    str(e)
                )
    
    def _notify_manager_new_request(self):
        """Отправка уведомления менеджеру о новом запросе"""
        if not self.sport_center_id or not self.sport_center_id.manager_id or not self.sport_center_id.manager_id.user_id:
            return
        
        self.env["mail.message"].create({
            "model": "final.training.booking",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Новый запрос на одобрение тренировки"),
            "body": _(
                "Тренер %s создал запрос на тренировку '%s' (%s - %s). "
                "Требуется ваше одобрение."
            ) % (
                self.trainer_id.name if self.trainer_id else _("Не указан"),
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
            ),
            "partner_ids": [(4, self.sport_center_id.manager_id.user_id.partner_id.id)],
        })

    def action_complete(self):
        """Завершение тренировки (списание баланса)"""
        self.ensure_one()
        
        # Проверяем что тренировка подтверждена
        if self.state != "confirmed":
            raise ValidationError(
                _("Можно завершить только подтвержденные тренировки.")
            )
        
        # Проверяем что тренировка еще не завершена
        if self.state == "completed":
            raise ValidationError(_("Тренировка уже завершена."))
        
        # Рассчитываем сумму списания для каждого клиента
        # Сумма = цена за час * продолжительность
        amount_per_client = self.price_per_hour * self.duration_hours
        
        # Проверяем баланс всех клиентов перед списанием
        insufficient_balance_clients = []
        for client in self.client_ids:
            if client.balance < amount_per_client:
                insufficient_balance_clients.append(
                    f"{client.name} (баланс: {client.balance} {client.balance_currency_id.symbol if client.balance_currency_id else ''}, требуется: {amount_per_client} {client.balance_currency_id.symbol if client.balance_currency_id else ''})"
                )
        
        if insufficient_balance_clients:
            raise ValidationError(
                _(
                    "Недостаточно средств на балансе у следующих клиентов:\n%s\n"
                    "Пополните баланс перед завершением тренировки."
                )
                % "\n".join(insufficient_balance_clients)
            )
        
        # Списываем средства с баланса всех клиентов
        transaction_model = self.env["final.balance.transaction"]
        for client in self.client_ids:
            description = _(
                "Списание за тренировку '%s' (%s - %s)"
            ) % (
                self.name or _("Тренировка"),
                self.start_datetime.strftime("%d.%m.%Y %H:%M") if self.start_datetime else "",
                self.end_datetime.strftime("%H:%M") if self.end_datetime else "",
            )
            
            try:
                transaction_model.action_withdrawal(
                    client.id,
                    amount_per_client,
                    self.id,
                    description,
                )
            except ValidationError as e:
                # Если произошла ошибка при списании, откатываем все транзакции
                raise ValidationError(
                    _(
                        "Ошибка при списании средств с баланса клиента '%s': %s"
                    )
                    % (client.name, str(e))
                )
        
        # Обновляем статус тренировки
        self.write({"state": "completed"})
        
        return True

    def action_cancel(self):
        """Отмена тренировки
        
        Если тренер инициирует отмену - требуется апрув менеджера.
        Если менеджер/директор - отмена происходит сразу.
        """
        self.ensure_one()
        
        # Проверяем права пользователя
        is_trainer = self.env.user.has_group("final.group_final_trainer")
        is_manager = self.env.user.has_group("final.group_final_manager")
        is_director = self.env.user.has_group("final.group_final_director")
        
        # Если тренер запрашивает отмену - открываем wizard для указания причины
        if is_trainer and not (is_manager or is_director):
            # Проверяем, что тренировка в статусе, который можно отменить
            if self.state not in ("draft", "pending_approval", "confirmed"):
                raise ValidationError(
                    _("Нельзя отменить тренировку в статусе '%s'.") % self._fields["state"]._description_string(self.env)
                )
            
            # Открываем wizard для запроса отмены
            return {
                "type": "ir.actions.act_window",
                "name": _("Запрос на отмену тренировки"),
                "res_model": "final.training.booking.cancel.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_booking_id": self.id,
                },
            }
        
        # Если менеджер или директор - отменяем сразу
        if is_manager or is_director:
            # Проверяем, что тренировка в статусе, который можно отменить
            if self.state in ("completed", "cancelled"):
                raise ValidationError(
                    _("Нельзя отменить тренировку в статусе '%s'.") % self._fields["state"]._description_string(self.env)
                )
            
            self.write({"state": "cancelled"})
            
            # Отправляем уведомления клиентам об отмене
            self._notify_clients_booking_cancelled()
            
            return True
        
        # Если пользователь не имеет прав
        raise ValidationError(_("У вас нет прав для отмены тренировки."))

    def action_set_draft(self):
        """Возврат в черновик"""
        self.write({
            "state": "draft",
            "approved_by": False,
            "approved_date": False,
        })
        return True
    
    def action_reschedule(self):
        """Запрос на перенос тренировки
        
        Если тренер инициирует перенос - требуется апрув менеджера.
        Если менеджер/директор - открывается wizard для переноса.
        """
        self.ensure_one()
        
        # Проверяем права пользователя
        is_trainer = self.env.user.has_group("final.group_final_trainer")
        is_manager = self.env.user.has_group("final.group_final_manager")
        is_director = self.env.user.has_group("final.group_final_director")
        
        # Проверяем, что тренировка в статусе, который можно перенести
        if self.state in ("completed", "cancelled"):
            raise ValidationError(
                _("Нельзя перенести тренировку в статусе '%s'.") % self._fields["state"]._description_string(self.env)
            )
        
        # Открываем wizard для переноса
        return {
            "type": "ir.actions.act_window",
            "name": _("Перенос тренировки"),
            "res_model": "final.training.booking.reschedule.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_booking_id": self.id,
                "default_is_trainer": is_trainer and not (is_manager or is_director),
            },
        }
    
    def action_approve_cancel(self):
        """Одобрение запроса на отмену менеджером"""
        self.ensure_one()
        
        # Проверка прав - только менеджер или директор
        if not self.env.user.has_group("final.group_final_manager") and not self.env.user.has_group("final.group_final_director"):
            raise ValidationError(_("Только менеджер или директор могут одобрять запросы на отмену."))
        
        # Проверка что есть запрос на отмену
        if not self.cancel_requested:
            raise ValidationError(_("Нет запроса на отмену для этой тренировки."))
        
        # Отменяем тренировку
        self.write({
            "state": "cancelled",
            "cancel_requested": False,
        })
        
        # Отправляем уведомления клиентам об отмене
        self._notify_clients_booking_cancelled()
        
        # Отправляем уведомление тренеру об одобрении отмены
        self._notify_trainer_cancel_approved()
        
        return True
    
    def action_reject_cancel(self):
        """Отклонение запроса на отмену менеджером"""
        self.ensure_one()
        
        # Проверка прав - только менеджер или директор
        if not self.env.user.has_group("final.group_final_manager") and not self.env.user.has_group("final.group_final_director"):
            raise ValidationError(_("Только менеджер или директор могут отклонять запросы на отмену."))
        
        # Проверка что есть запрос на отмену
        if not self.cancel_requested:
            raise ValidationError(_("Нет запроса на отмену для этой тренировки."))
        
        # Открываем wizard для указания причины отклонения
        return {
            "type": "ir.actions.act_window",
            "name": _("Отклонить запрос на отмену"),
            "res_model": "final.training.booking.reject.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_booking_id": self.id,
            },
        }
    
    def action_reject_cancel_confirm(self, rejection_reason=""):
        """Подтверждение отклонения запроса на отмену с причиной"""
        self.ensure_one()
        
        # Подготавливаем значения для обновления
        update_vals = {
            "cancel_requested": False,
            "cancel_requested_by": False,
            "cancel_requested_date": False,
            "cancel_request_reason": False,
        }
        
        # Если тренировка была в статусе "pending_approval" из-за запроса на отмену,
        # возвращаем её в статус "confirmed" после отклонения запроса
        if self.state == "pending_approval":
            update_vals["state"] = "confirmed"
        
        # Сбрасываем запрос на отмену
        self.write(update_vals)
        
        # Отправляем уведомление тренеру об отклонении отмены
        self._notify_trainer_cancel_rejected(rejection_reason)
        
        return True
    
    def action_approve_reschedule(self):
        """Одобрение запроса на перенос менеджером"""
        self.ensure_one()
        
        # Проверка прав - только менеджер или директор
        if not self.env.user.has_group("final.group_final_manager") and not self.env.user.has_group("final.group_final_director"):
            raise ValidationError(_("Только менеджер или директор могут одобрять запросы на перенос."))
        
        # Проверка что есть запрос на перенос
        if not self.reschedule_requested:
            raise ValidationError(_("Нет запроса на перенос для этой тренировки."))
        
        if not self.reschedule_new_start_datetime or not self.reschedule_new_end_datetime:
            raise ValidationError(_("Не указано новое время для переноса."))
        
        # Сохраняем старое время для уведомлений
        old_start = self.start_datetime
        old_end = self.end_datetime
        old_court = self.tennis_court_id
        
        # Переносим тренировку
        update_vals = {
            "start_datetime": self.reschedule_new_start_datetime,
            "end_datetime": self.reschedule_new_end_datetime,
            "reschedule_requested": False,
            "reschedule_requested_by": False,
            "reschedule_requested_date": False,
            "reschedule_reason": False,
        }
        
        # Если указан новый корт - обновляем его
        if self.reschedule_new_court_id:
            update_vals["tennis_court_id"] = self.reschedule_new_court_id.id
        
        # Сбрасываем поля переноса
        update_vals.update({
            "reschedule_new_start_datetime": False,
            "reschedule_new_end_datetime": False,
            "reschedule_new_court_id": False,
        })
        
        # Если тренировка была в статусе "pending_approval" из-за запроса на перенос,
        # возвращаем её в статус "confirmed" после одобрения
        if self.state == "pending_approval":
            update_vals["state"] = "confirmed"
        
        self.write(update_vals)
        
        # Отправляем уведомления клиентам о переносе
        self._notify_clients_booking_rescheduled(old_start, old_end, old_court)
        
        # Отправляем уведомление тренеру об одобрении переноса
        self._notify_trainer_reschedule_approved()
        
        return True
    
    def action_reject_reschedule(self):
        """Отклонение запроса на перенос менеджером"""
        self.ensure_one()
        
        # Проверка прав - только менеджер или директор
        if not self.env.user.has_group("final.group_final_manager") and not self.env.user.has_group("final.group_final_director"):
            raise ValidationError(_("Только менеджер или директор могут отклонять запросы на перенос."))
        
        # Проверка что есть запрос на перенос
        if not self.reschedule_requested:
            raise ValidationError(_("Нет запроса на перенос для этой тренировки."))
        
        # Открываем wizard для указания причины отклонения
        return {
            "type": "ir.actions.act_window",
            "name": _("Отклонить запрос на перенос"),
            "res_model": "final.training.booking.reject.reschedule.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_booking_id": self.id,
            },
        }
    
    def action_reject_reschedule_confirm(self, rejection_reason=""):
        """Подтверждение отклонения запроса на перенос с причиной"""
        self.ensure_one()
        
        # Подготавливаем значения для обновления
        update_vals = {
            "reschedule_requested": False,
            "reschedule_requested_by": False,
            "reschedule_requested_date": False,
            "reschedule_new_start_datetime": False,
            "reschedule_new_end_datetime": False,
            "reschedule_new_court_id": False,
            "reschedule_reason": False,
        }
        
        # Если тренировка была в статусе "pending_approval" из-за запроса на перенос,
        # возвращаем её в статус "confirmed" после отклонения запроса
        if self.state == "pending_approval":
            update_vals["state"] = "confirmed"
        
        # Сбрасываем запрос на перенос
        self.write(update_vals)
        
        # Отправляем уведомление тренеру об отклонении переноса
        self._notify_trainer_reschedule_rejected(rejection_reason)
        
        return True
    
    def read(self, fields=None, load='_classic_read'):
        """Переопределяем read для менеджера, чтобы он мог читать trainer_id"""
        # Если менеджер читает запись, используем sudo() для чтения всех полей
        # Это необходимо, так как менеджеру нужно читать trainer_id, к которому у него может не быть доступа
        if self.env.user.has_group("final.group_final_manager"):
            # Используем sudo() для чтения записей, чтобы обойти правила доступа к hr.employee
            # Важно: вызываем super() напрямую с sudo(), чтобы избежать рекурсии
            try:
                return super(FinalTrainingBooking, self.sudo()).read(fields=fields, load=load)
            except AttributeError as e:
                # Если возникает ошибка с _unknown объектами, используем альтернативный подход
                if "'_unknown' object has no attribute 'id'" in str(e) or "'_unknown'" in str(e):
                    # Читаем данные напрямую из записей, обрабатывая каждое поле отдельно
                    result = []
                    for record in self.sudo():
                        record_data = {'id': record.id}
                        
                        # Определяем, какие поля нужно прочитать
                        if fields is None:
                            # Если поля не указаны, читаем все поля модели
                            fields_to_read = list(self._fields.keys())
                        else:
                            fields_to_read = fields
                        
                        # Читаем каждое поле отдельно с обработкой ошибок
                        for field_name in fields_to_read:
                            # Пропускаем служебные поля и поля с точками (related поля)
                            if field_name.startswith('_') or '.' in field_name:
                                continue
                            
                            field = self._fields.get(field_name)
                            if field:
                                try:
                                    if field.type == 'many2one':
                                        # Для Many2one полей читаем с обработкой _unknown
                                        try:
                                            value = record[field_name]
                                            if value and hasattr(value, 'id'):
                                                record_data[field_name] = value.id
                                            else:
                                                record_data[field_name] = False
                                        except (AttributeError, ValueError):
                                            record_data[field_name] = False
                                    elif field.type == 'many2many':
                                        # Для Many2many полей читаем список ID
                                        try:
                                            value = record[field_name]
                                            record_data[field_name] = value.ids if value else []
                                        except (AttributeError, ValueError):
                                            record_data[field_name] = []
                                    elif field.type == 'one2many':
                                        # Для One2many полей читаем список ID
                                        try:
                                            value = record[field_name]
                                            record_data[field_name] = value.ids if value else []
                                        except (AttributeError, ValueError):
                                            record_data[field_name] = []
                                    else:
                                        # Для остальных полей читаем как обычно
                                        try:
                                            record_data[field_name] = record[field_name]
                                        except (AttributeError, ValueError):
                                            record_data[field_name] = False
                                except Exception:
                                    record_data[field_name] = False
                        
                        result.append(record_data)
                    
                    return result
                else:
                    raise
        
        return super().read(fields=fields, load=load)
    
    def action_generate_recurring_bookings(self):
        """Генерация тренировок для повторяющейся тренировки"""
        self.ensure_one()
        
        if not self.is_recurring or not self.recurring_id:
            raise ValidationError(_("Эта тренировка не является повторяющейся."))
        
        if self.state != "confirmed":
            raise ValidationError(_("Можно генерировать тренировки только для подтвержденных повторяющихся тренировок."))
        
        # Используем метод генерации из шаблона
        return self.recurring_id.generate_bookings()
    
    @api.model
    def action_open_pending_approvals(self):
        """Открывает список запросов на одобрение для менеджера"""
        user = self.env.user
        
        if user.has_group("final.group_final_manager"):
            # Для менеджера - только запросы его СЦ
            # Используем sudo() для чтения employee_id, чтобы обойти правила доступа
            manager_employee = user.sudo().employee_id
            if manager_employee and manager_employee.is_final_manager:
                center = self.env["final.sport.center"].search([
                    ("manager_id", "=", manager_employee.id),
                ], limit=1)
                if center:
                    domain = [
                        ("state", "=", "pending_approval"),
                        ("sport_center_id", "=", center.id),
                    ]
                else:
                    domain = [("id", "=", False)]  # Пустой список
            else:
                domain = [("id", "=", False)]
        elif user.has_group("final.group_final_director"):
            # Для директора - все запросы
            domain = [("state", "=", "pending_approval")]
        else:
            domain = [("id", "=", False)]
        
        # Получаем ID представлений для явного указания
        list_view_id = self.env.ref("final.view_final_training_booking_list").id
        form_view_id = self.env.ref("final.view_final_training_booking_form").id
        
        return {
            "type": "ir.actions.act_window",
            "name": _("Запросы на одобрение"),
            "res_model": "final.training.booking",
            "view_mode": "list,form",
            "views": [(list_view_id, "list"), (form_view_id, "form")],
            "domain": domain,
            "context": {
                "search_default_pending_approval": 1,
                "default_state": "pending_approval",
                # Добавляем фильтры по дате, тренеру и корту для удобства менеджера
            },
            "help": _("Список тренировок, ожидающих одобрения менеджера. Кликните на запись, чтобы открыть форму с кнопками 'Одобрить' и 'Отклонить'."),
        }
    
    @api.model
    def _get_upcoming_week_domain(self):
        """Возвращает домен для фильтра 'Ближайшие' (неделя вперед)"""
        now = fields.Datetime.now()
        week_later = now + timedelta(days=7)
        return [
            ('start_datetime', '>=', now),
            ('start_datetime', '<', week_later),
        ]

