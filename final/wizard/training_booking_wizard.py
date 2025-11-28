# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class TrainingBookingWizard(models.TransientModel):
    _name = "final.training.booking.wizard"
    _description = "Мастер записи на тренировку"

    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        required=True,
        domain="[('id', 'in', available_center_ids)]",
    )
    
    # Computed поле для домена СЦ (для тренера - только его СЦ)
    available_center_ids = fields.Many2many(
        "final.sport.center",
        "final_training_booking_wizard_center_rel",
        "wizard_id",
        "center_id",
        string="Доступные СЦ",
        compute="_compute_available_center_ids",
        store=False,
    )
    tennis_court_id = fields.Many2one(
        "final.tennis.court",
        string="Теннисный корт",
        required=True,
        domain="[('sport_center_id', '=', sport_center_id)]",
    )
    training_type_id = fields.Many2one(
        "final.training.type",
        string="Тип тренировки",
        required=True,
    )
    trainer_id = fields.Many2one(
        "hr.employee",
        string="Тренер",
        required=True,
    )
    date = fields.Date(
        string="Дата",
        required=True,
        default=fields.Date.today,
    )
    start_time = fields.Float(
        string="Время начала",
        required=True,
        help="Время начала в формате часов (например, 14.5 = 14:30)",
    )
    duration = fields.Float(
        string="Продолжительность (часов)",
        required=True,
        default=1.0,
        help="Продолжительность тренировки в часах (минимум 1 час, шаг 1 час)",
    )
    client_ids = fields.Many2many(
        "res.partner",
        "final_training_booking_wizard_partner_rel",
        "wizard_id",
        "partner_id",
        string="Клиенты",
        required=True,
        domain="[('is_company', '=', False)]",
    )
    is_recurring = fields.Boolean(
        string="Повторяющаяся тренировка",
        default=False,
    )
    recurring_end_date = fields.Date(
        string="Дата окончания повтора",
        help="До какой даты повторять тренировку",
    )
    recurring_days_of_week = fields.Char(
        string="Дни недели для повтора",
        help="Через запятую дни недели (0=Понедельник, 6=Воскресенье). Например: 0,2,4",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="sport_center_id.currency_id",
        readonly=True,
    )
    
    # Computed поле для readonly для тренера
    is_trainer_readonly = fields.Boolean(
        string="Тренер readonly",
        compute="_compute_is_trainer_readonly",
        default=False,
    )
    
    # Computed поле для домена тренеров
    available_trainer_ids = fields.Many2many(
        "hr.employee",
        "final_training_booking_wizard_trainer_rel",
        "wizard_id",
        "employee_id",
        string="Доступные тренеры",
        compute="_compute_available_trainer_ids",
        store=False,
    )
    
    # Информационные поля для отображения
    client_count_info = fields.Char(
        string="Количество клиентов",
        compute="_compute_client_count_info",
        readonly=True,
    )
    available_slots_info = fields.Html(
        string="Доступные слоты",
        compute="_compute_available_slots_info",
        readonly=True,
    )

    @api.depends()
    def _compute_available_center_ids(self):
        """Вычисляет список доступных СЦ (для тренера - только его СЦ)"""
        for record in self:
            user = self.env.user
            if user.has_group("final.group_final_trainer"):
                # Для тренера - только его СЦ
                trainer_employee = user.employee_id
                if trainer_employee and trainer_employee.is_final_trainer:
                    record.available_center_ids = trainer_employee.trainer_center_ids
                else:
                    record.available_center_ids = False
            elif user.has_group("final.group_final_manager"):
                # Для менеджера - только его СЦ
                manager_employee = user.employee_id
                if manager_employee and manager_employee.is_final_manager:
                    center = self.env["final.sport.center"].search([
                        ("manager_id", "=", manager_employee.id),
                    ], limit=1)
                    if center:
                        record.available_center_ids = center
                    else:
                        record.available_center_ids = False
                else:
                    record.available_center_ids = False
            else:
                # Для директора - все СЦ (не ограничиваем)
                record.available_center_ids = self.env["final.sport.center"].search([])
    
    @api.depends("sport_center_id")
    def _compute_available_trainer_ids(self):
        """Вычисляет список доступных тренеров для выбранного СЦ"""
        for record in self:
            if record.sport_center_id:
                # Находим тренеров этого СЦ через final.center.trainer
                center_trainers = self.env["final.center.trainer"].search([
                    ("sport_center_id", "=", record.sport_center_id.id),
                ])
                record.available_trainer_ids = center_trainers.mapped("employee_id")
            else:
                record.available_trainer_ids = False
    
    @api.depends()
    def _compute_is_trainer_readonly(self):
        """Делает поле trainer_id readonly для тренера"""
        for record in self:
            record.is_trainer_readonly = self.env.user.has_group("final.group_final_trainer")
    
    @api.depends("client_ids", "training_type_id")
    def _compute_client_count_info(self):
        """Показывает информацию о количестве клиентов"""
        for record in self:
            client_count = len(record.client_ids)
            if not record.training_type_id:
                record.client_count_info = f"Выбрано клиентов: {client_count}"
                continue
            
            min_clients = record.training_type_id.min_clients
            max_clients = record.training_type_id.max_clients
            
            if client_count < min_clients:
                record.client_count_info = (
                    f"Выбрано клиентов: {client_count} (минимум {min_clients})"
                )
            elif client_count > max_clients:
                record.client_count_info = (
                    f"Выбрано клиентов: {client_count} (максимум {max_clients})"
                )
            else:
                record.client_count_info = (
                    f"Выбрано клиентов: {client_count} из {max_clients if max_clients == min_clients else f'{min_clients}-{max_clients}'} ✓"
                )

    @api.depends("tennis_court_id", "date", "sport_center_id")
    def _compute_available_slots_info(self):
        """Вычисляет и показывает занятые/свободные слоты"""
        for record in self:
            if not record.tennis_court_id or not record.date or not record.sport_center_id:
                record.available_slots_info = ""
                continue
            
            # Получаем рабочие часы центра
            center = record.sport_center_id
            work_start = int(center.work_time_start)
            work_end = int(center.work_time_end)
            
            # Получаем все занятые слоты на этот день
            start_of_day = fields.Datetime.to_datetime(record.date).replace(hour=0, minute=0, second=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            bookings = self.env["final.training.booking"].search([
                ("tennis_court_id", "=", record.tennis_court_id.id),
                ("start_datetime", ">=", start_of_day),
                ("start_datetime", "<", end_of_day),
                ("state", "in", ["draft", "pending_approval", "confirmed"]),
            ])
            
            # Формируем HTML с информацией о занятости
            html_parts = ["<div style='margin: 10px 0;'>"]
            html_parts.append(f"<strong>Рабочие часы: {work_start}:00 - {work_end}:00</strong><br/>")
            
            if bookings:
                html_parts.append("<br/><strong>Занятые слоты:</strong><ul>")
                for booking in bookings:
                    start = fields.Datetime.context_timestamp(record, booking.start_datetime)
                    end = fields.Datetime.context_timestamp(record, booking.end_datetime)
                    trainer_name = booking.trainer_id.name if booking.trainer_id else "Не указан"
                    clients = ", ".join(booking.client_ids.mapped("name")) if booking.client_ids else "Нет клиентов"
                    html_parts.append(
                        f"<li>{start.strftime('%H:%M')} - {end.strftime('%H:%M')} "
                        f"(Тренер: {trainer_name}, Клиенты: {clients})</li>"
                    )
                html_parts.append("</ul>")
            else:
                html_parts.append("<br/><em>Корт свободен весь день</em>")
            
            html_parts.append("</div>")
            record.available_slots_info = "".join(html_parts)

    @api.model
    def default_get(self, fields_list):
        """Устанавливает значения по умолчанию"""
        res = super().default_get(fields_list)
        user = self.env.user
        
        # Автозаполнение тренера для тренера
        if user.has_group("final.group_final_trainer"):
            trainer_employee = user.employee_id
            if trainer_employee and trainer_employee.is_final_trainer:
                # Автозаполнение СЦ из первого центра тренера
                if trainer_employee.trainer_center_ids:
                    res["sport_center_id"] = trainer_employee.trainer_center_ids[0].id
                    # Устанавливаем тренера (он же инициирует тренировку)
                    res["trainer_id"] = trainer_employee.id
        
        # Автозаполнение СЦ для менеджера
        elif user.has_group("final.group_final_manager"):
            manager_employee = user.employee_id
            if manager_employee and manager_employee.is_final_manager:
                # Находим СЦ где менеджер является менеджером
                center = self.env["final.sport.center"].search([
                    ("manager_id", "=", manager_employee.id),
                ], limit=1)
                if center:
                    res["sport_center_id"] = center.id
        
        # Если СЦ передан в контексте
        if "default_sport_center_id" in self.env.context:
            res["sport_center_id"] = self.env.context["default_sport_center_id"]
        
        return res
    

    @api.onchange("sport_center_id")
    def _onchange_sport_center_id(self):
        """Обновляет домен корта и тренера при изменении СЦ"""
        # Обновляем computed поле available_trainer_ids
        self._compute_available_trainer_ids()
        
        if self.sport_center_id:
            # Обновляем домен корта
            self.tennis_court_id = False
            
            # Получаем список ID тренеров из computed поля
            trainer_ids = self.available_trainer_ids.ids
            
            # Если нет тренеров в этом СЦ
            if not trainer_ids:
                self.trainer_id = False
                return {
                    "domain": {
                        "tennis_court_id": [("sport_center_id", "=", self.sport_center_id.id)],
                    },
                    "warning": {
                        "title": _("Нет тренеров"),
                        "message": _("В выбранном спортивном центре нет привязанных тренеров."),
                    }
                }
            
            # Если текущий пользователь - тренер, проверяем и устанавливаем его
            user = self.env.user
            if user.has_group("final.group_final_trainer"):
                trainer_employee = user.employee_id
                if trainer_employee and trainer_employee.is_final_trainer:
                    if trainer_employee.id in trainer_ids:
                        # Тренер привязан к этому СЦ - оставляем его выбранным
                        self.trainer_id = trainer_employee.id
                    else:
                        # Тренер не привязан к этому СЦ - сбрасываем выбор
                        self.trainer_id = False
            else:
                # Для менеджера - сбрасываем выбор тренера, если он не из этого СЦ
                if self.trainer_id and self.trainer_id.id not in trainer_ids:
                    self.trainer_id = False
            
            return {
                "domain": {
                    "tennis_court_id": [("sport_center_id", "=", self.sport_center_id.id)],
                }
            }
        else:
            self.tennis_court_id = False
            self.trainer_id = False
            return {
                "domain": {
                    "tennis_court_id": [],
                }
            }

    @api.onchange("trainer_id")
    def _onchange_trainer_id(self):
        """Проверка что выбранный тренер принадлежит выбранному СЦ"""
        if self.trainer_id and self.sport_center_id:
            # Проверяем через final.center.trainer
            center_trainer = self.env["final.center.trainer"].search([
                ("sport_center_id", "=", self.sport_center_id.id),
                ("employee_id", "=", self.trainer_id.id),
            ], limit=1)
            
            if not center_trainer:
                self.trainer_id = False
                return {
                    "warning": {
                        "title": _("Недопустимый тренер"),
                        "message": _(
                            "Тренер '%s' не привязан к спортивному центру '%s'. "
                            "Выберите тренера из списка этого СЦ."
                        ) % (self.trainer_id.name, self.sport_center_id.name),
                    }
                }
    
    @api.onchange("training_type_id", "client_ids")
    def _onchange_training_type_or_clients(self):
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

    @api.onchange("date", "start_time", "duration", "tennis_court_id", "sport_center_id")
    def _onchange_time_slot(self):
        """Проверка доступности времени и рабочих часов"""
        if not all([self.date, self.start_time is not None, self.duration, self.tennis_court_id, self.sport_center_id]):
            return
        
        # Формируем datetime для начала и окончания
        start_datetime = fields.Datetime.to_datetime(self.date)
        start_hour = int(self.start_time)
        start_minute = int((self.start_time - start_hour) * 60)
        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)
        
        end_datetime = start_datetime + timedelta(hours=self.duration)
        
        # Проверка рабочих часов центра
        center = self.sport_center_id
        start_hour_float = start_hour + start_minute / 60.0
        end_hour_float = start_hour_float + self.duration
        
        if start_hour_float < center.work_time_start or end_hour_float > center.work_time_end:
            return {
                "warning": {
                    "title": _("Вне рабочих часов"),
                    "message": _(
                        "Тренировка должна быть в рабочие часы центра '%s' "
                        "(с %.1f до %.1f часов). "
                        "Выбранное время: %.1f - %.1f часов."
                    ) % (
                        center.name,
                        center.work_time_start,
                        center.work_time_end,
                        start_hour_float,
                        end_hour_float,
                    ),
                }
            }
        
        # Проверяем пересечение с существующими записями
        bookings = self.env["final.training.booking"].search([
            ("tennis_court_id", "=", self.tennis_court_id.id),
            ("state", "in", ["draft", "pending_approval", "confirmed"]),
            ("start_datetime", "<", end_datetime),
            ("end_datetime", ">", start_datetime),
        ], limit=1)
        
        if bookings:
            return {
                "warning": {
                    "title": _("Время занято"),
                    "message": _(
                        "Корт '%s' уже занят в это время. "
                        "Проверьте доступные слоты ниже."
                    ) % self.tennis_court_id.name,
                }
            }

    @api.constrains("duration")
    def _check_duration(self):
        """Проверка продолжительности"""
        for record in self:
            if record.duration < 1:
                raise ValidationError(_("Минимальная продолжительность тренировки - 1 час."))
            # Проверяем что продолжительность - целое число (кратно 1 часу)
            if abs(record.duration - round(record.duration)) > 0.01:
                raise ValidationError(_("Продолжительность должна быть кратной 1 часу (1, 2, 3... часов)."))

    @api.constrains("training_type_id", "client_ids")
    def _check_client_count(self):
        """Проверка количества клиентов"""
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

    def action_create_booking(self):
        """Создает запись на тренировку"""
        self.ensure_one()
        
        # Валидации
        if not all([self.sport_center_id, self.tennis_court_id, self.trainer_id, 
                   self.training_type_id, self.date, self.start_time is not None, 
                   self.duration, self.client_ids]):
            raise ValidationError(_("Заполните все обязательные поля."))
        
        # Формируем datetime для начала
        start_datetime = fields.Datetime.to_datetime(self.date)
        start_hour = int(self.start_time)
        start_minute = int((self.start_time - start_hour) * 60)
        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)
        
        # Формируем datetime для окончания
        end_datetime = start_datetime + timedelta(hours=self.duration)
        
        # Финальная проверка рабочих часов центра
        center = self.sport_center_id
        start_hour_float = start_hour + start_minute / 60.0
        end_hour_float = start_hour_float + self.duration
        
        if start_hour_float < center.work_time_start or end_hour_float > center.work_time_end:
            raise ValidationError(
                _(
                    "Тренировка должна быть в рабочие часы центра '%s' "
                    "(с %.1f до %.1f часов). "
                    "Выбранное время: %.1f - %.1f часов."
                ) % (
                    center.name,
                    center.work_time_start,
                    center.work_time_end,
                    start_hour_float,
                    end_hour_float,
                )
            )
        
        # Проверяем, что тренер привязан к СЦ
        if self.sport_center_id not in self.trainer_id.trainer_center_ids:
            raise ValidationError(
                _("Тренер '%s' не привязан к спортивному центру '%s'.") %
                (self.trainer_id.name, self.sport_center_id.name)
            )
        
        # Определяем статус в зависимости от роли пользователя
        user = self.env.user
        if user.has_group("final.group_final_trainer"):
            state = "pending_approval"  # Тренер создает - требуется апрув
        else:
            state = "confirmed"  # Менеджер создает - сразу подтверждено
        
        # Создаем запись
        booking = self.env["final.training.booking"].create({
            "sport_center_id": self.sport_center_id.id,
            "tennis_court_id": self.tennis_court_id.id,
            "trainer_id": self.trainer_id.id,
            "training_type_id": self.training_type_id.id,
            "client_ids": [(6, 0, self.client_ids.ids)],
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "state": state,
            "created_by": user.id,
            "is_recurring": self.is_recurring,
        })
        
        # TODO: Повторяющиеся тренировки будут реализованы позже
        
        # Возвращаем action для открытия созданной записи
        return {
            "type": "ir.actions.act_window",
            "name": _("Тренировка создана"),
            "res_model": "final.training.booking",
            "res_id": booking.id,
            "view_mode": "form",
            "target": "current",
        }

