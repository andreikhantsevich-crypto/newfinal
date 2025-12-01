# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


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
        if not self.trainer_id or not self.trainer_id.user_id:
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
            "partner_ids": [(4, self.trainer_id.user_id.partner_id.id)],
        })
    
    def _notify_trainer_rejection(self):
        """Отправка уведомления тренеру об отклонении"""
        if not self.trainer_id or not self.trainer_id.user_id:
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
            "partner_ids": [(4, self.trainer_id.user_id.partner_id.id)],
        })
    
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

