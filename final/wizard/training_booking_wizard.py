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
        domain="[('id', 'in', available_trainer_ids)]",
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
        domain="[('is_company', '=', False), ('telegram_user_id', '!=', False), ('sport_center_ids', 'in', [sport_center_id])]",
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
        compute_sudo=True,  # Используем sudo для обхода правил доступа при вычислении
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
                # Используем sudo() для чтения employee_id, чтобы обойти правила доступа
                trainer_employee = user.sudo().employee_id
                if trainer_employee and trainer_employee.is_final_trainer:
                    # Читаем напрямую через final.center.trainer с sudo(), чтобы гарантировать получение всех СЦ
                    # Это обходит проблемы с вычисляемым полем trainer_center_ids
                    center_trainer_records = self.env["final.center.trainer"].sudo().search([
                        ("employee_id", "=", trainer_employee.id),
                    ])
                    center_ids = center_trainer_records.mapped("sport_center_id")
                    record.available_center_ids = center_ids
                else:
                    record.available_center_ids = False
            elif user.has_group("final.group_final_manager"):
                # Для менеджера - только его СЦ
                # Используем sudo() для чтения employee_id, чтобы обойти правила доступа
                manager_employee = user.sudo().employee_id
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
        user = self.env.user
        is_trainer = user.has_group("final.group_final_trainer")
        
        for record in self:
            # Для тренера не вычисляем список тренеров (поле trainer_id readonly)
            if is_trainer:
                record.available_trainer_ids = False
                continue
                
            if record.sport_center_id:
                # Находим тренеров этого СЦ через final.center.trainer
                # Используем sudo() чтобы избежать проблем с правами доступа при чтении hr.employee
                center_trainers = self.env["final.center.trainer"].sudo().search([
                    ("sport_center_id", "=", record.sport_center_id.id),
                ])
                # Используем sudo() при чтении employee_id записей, чтобы обойти правила доступа
                trainer_ids = center_trainers.mapped("employee_id.id")
                record.available_trainer_ids = self.env["hr.employee"].sudo().browse(trainer_ids) if trainer_ids else False
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
            # Используем sudo() для чтения employee_id, чтобы обойти правила доступа
            trainer_employee = user.sudo().employee_id
            if trainer_employee and trainer_employee.is_final_trainer:
                # Автозаполнение СЦ из первого центра тренера
                # Читаем напрямую через final.center.trainer с sudo(), чтобы гарантировать получение всех СЦ
                center_trainer_records = self.env["final.center.trainer"].sudo().search([
                    ("employee_id", "=", trainer_employee.id),
                ])
                center_ids = center_trainer_records.mapped("sport_center_id")
                if center_ids:
                    res["sport_center_id"] = center_ids[0].id
                    # Устанавливаем тренера (он же инициирует тренировку)
                    # Используем только ID, чтобы избежать проверки доступа при установке значения
                    res["trainer_id"] = trainer_employee.id
        
        # Автозаполнение СЦ для менеджера
        elif user.has_group("final.group_final_manager"):
            # Используем sudo() для чтения employee_id, чтобы обойти правила доступа
            manager_employee = user.sudo().employee_id
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
    
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Переопределяем для динамического домена sport_center_id"""
        res = super().fields_get(allfields=allfields, attributes=attributes)
        
        if 'sport_center_id' in res:
            user = self.env.user
            center_ids = []
            
            if user.has_group("final.group_final_trainer"):
                trainer_employee = user.sudo().employee_id
                if trainer_employee and trainer_employee.is_final_trainer:
                    # Читаем напрямую через final.center.trainer с sudo()
                    center_trainer_records = self.env["final.center.trainer"].sudo().search([
                        ("employee_id", "=", trainer_employee.id),
                    ])
                    center_ids = center_trainer_records.mapped("sport_center_id").ids
            elif user.has_group("final.group_final_manager"):
                manager_employee = user.sudo().employee_id
                if manager_employee and manager_employee.is_final_manager:
                    center = self.env["final.sport.center"].search([
                        ("manager_id", "=", manager_employee.id),
                    ], limit=1)
                    if center:
                        center_ids = [center.id]
            else:
                # Для директора - все СЦ
                center_ids = self.env["final.sport.center"].search([]).ids
            
            if center_ids:
                res['sport_center_id']['domain'] = [('id', 'in', center_ids)]
            else:
                res['sport_center_id']['domain'] = [('id', '=', False)]
        
        return res
    

    @api.onchange("sport_center_id")
    def _onchange_sport_center_id(self):
        """Обновляет домен корта и тренера при изменении СЦ"""
        user = self.env.user
        is_trainer = user.has_group("final.group_final_trainer")
        
        if self.sport_center_id:
            # Обновляем домен корта
            self.tennis_court_id = False
            
            # Для тренера - поле readonly, не нужно вычислять домен и список тренеров
            if is_trainer:
                # Используем sudo() для чтения employee_id, чтобы обойти правила доступа
                trainer_employee = user.sudo().employee_id
                if trainer_employee and trainer_employee.is_final_trainer:
                    # Проверяем, привязан ли тренер к выбранному СЦ
                    # Читаем напрямую через final.center.trainer с sudo(), чтобы гарантировать получение всех СЦ
                    center_trainer_record = self.env["final.center.trainer"].sudo().search([
                        ("employee_id", "=", trainer_employee.id),
                        ("sport_center_id", "=", self.sport_center_id.id),
                    ], limit=1)
                    if center_trainer_record:
                        # Тренер привязан к этому СЦ - устанавливаем его
                        # Используем sudo() при установке значения через write(), чтобы обойти проверку доступа
                        self.sudo().write({"trainer_id": trainer_employee.id})
                    else:
                        # Тренер не привязан к этому СЦ - сбрасываем выбор
                        self.trainer_id = False
                        return {
                            "domain": {
                                "tennis_court_id": [("sport_center_id", "=", self.sport_center_id.id)],
                            },
                            "warning": {
                                "title": _("Ошибка"),
                                "message": _("Вы не привязаны к этому спортивному центру."),
                            }
                        }
                
                # Для тренера не устанавливаем домен на trainer_id (поле readonly)
                return {
                    "domain": {
                        "tennis_court_id": [("sport_center_id", "=", self.sport_center_id.id)],
                    }
                }
            
            # Для менеджера и директора - вычисляем список тренеров
            # Обновляем computed поле available_trainer_ids (домен обновится автоматически)
            self._compute_available_trainer_ids()
            
            # Используем sudo() для получения ID тренеров, чтобы обойти правила доступа
            trainer_ids = self.env["final.center.trainer"].sudo().search([
                ("sport_center_id", "=", self.sport_center_id.id),
            ]).mapped("employee_id.id")
            
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
            # Используем sudo() чтобы избежать проблем с правами доступа при чтении hr.employee
            center_trainer = self.env["final.center.trainer"].sudo().search([
                ("sport_center_id", "=", self.sport_center_id.id),
                ("employee_id", "=", self.trainer_id.id),
            ], limit=1)
            
            if not center_trainer:
                # Используем sudo() для чтения имени тренера, чтобы обойти правила доступа
                trainer_name = self.trainer_id.sudo().name if self.trainer_id else _("Неизвестный тренер")
                self.trainer_id = False
                return {
                    "warning": {
                        "title": _("Недопустимый тренер"),
                        "message": _(
                            "Тренер '%s' не привязан к спортивному центру '%s'. "
                            "Выберите тренера из списка этого СЦ."
                        ) % (trainer_name, self.sport_center_id.name),
                    }
                }
    
    @api.onchange("training_type_id")
    def _onchange_training_type_id(self):
        """Проверяет соответствие количества клиентов при выборе типа тренировки"""
        # Если тип тренировки выбран, но клиентов нет или их количество не соответствует - сбрасываем тип
        if self.training_type_id:
            client_count = len(self.client_ids) if self.client_ids else 0
            min_clients = self.training_type_id.min_clients
            max_clients = self.training_type_id.max_clients
            
            # Если количество клиентов не соответствует требованиям типа тренировки
            if client_count < min_clients or client_count > max_clients:
                old_type_name = self.training_type_id.name
                required_text = (
                    f"ровно {min_clients}" if min_clients == max_clients 
                    else f"от {min_clients} до {max_clients}"
                )
                self.training_type_id = False
                return {
                    "warning": {
                        "title": _("Несоответствие типа тренировки"),
                        "message": _(
                            "Тип тренировки '%s' требует %s клиент(ов), "
                            "а вы выбрали %d. "
                            "Сначала выберите правильное количество клиентов, "
                            "затем выберите тип тренировки."
                        ) % (old_type_name, required_text, client_count),
                    }
                }
    
    @api.onchange("client_ids")
    def _onchange_client_ids(self):
        """Проверяет соответствие типа тренировки при изменении клиентов"""
        if self.training_type_id and self.client_ids:
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

    @api.onchange("tennis_court_id")
    def _onchange_tennis_court_id(self):
        """Проверка рабочих часов и занятости при выборе корта"""
        if not self.tennis_court_id or not self.sport_center_id:
            return
        
        # Если дата и время уже заполнены, проверяем соответствие рабочим часам
        if self.date and self.start_time is not None and self.duration:
            # Пропускаем проверку, если время равно 0.0 (дефолтное значение) - пользователь еще не выбрал время
            if self.start_time == 0.0:
                return
            
            # Формируем datetime для начала и окончания
            start_datetime = fields.Datetime.to_datetime(self.date)
            start_hour = int(self.start_time)
            start_minute = int((self.start_time - start_hour) * 60)
            start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)
            
            end_datetime = start_datetime + timedelta(hours=self.duration)
            
            # Проверка на прошлое время (только если время реально выбрано пользователем)
            now = fields.Datetime.now()
            if start_datetime < now:
                old_court_name = self.tennis_court_id.name
                self.tennis_court_id = False
                return {
                    "warning": {
                        "title": _("Время в прошлом"),
                        "message": _(
                            "Нельзя создать тренировку в прошлом. "
                            "Выбранное время: %s. "
                            "Текущее время: %s. "
                            "Пожалуйста, сначала выберите время в будущем, "
                            "затем выберите корт."
                        ) % (
                            start_datetime.strftime("%d.%m.%Y %H:%M"),
                            now.strftime("%d.%m.%Y %H:%M"),
                        ),
                    }
                }
            
            # Проверка рабочих часов центра
            center = self.sport_center_id
            start_hour_float = start_hour + start_minute / 60.0
            end_hour_float = start_hour_float + self.duration
            
            if start_hour_float < center.work_time_start or end_hour_float > center.work_time_end:
                old_court_name = self.tennis_court_id.name
                self.tennis_court_id = False
                return {
                    "warning": {
                        "title": _("Вне рабочих часов"),
                        "message": _(
                            "Выбранное время тренировки не соответствует рабочим часам центра '%s' "
                            "(с %.1f до %.1f часов). "
                            "Выбранное время: %.1f - %.1f часов. "
                            "Пожалуйста, сначала выберите время в пределах рабочих часов, "
                            "затем выберите корт."
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
                old_court_name = self.tennis_court_id.name
                self.tennis_court_id = False
                return {
                    "warning": {
                        "title": _("Время занято"),
                        "message": _(
                            "Корт '%s' уже занят в это время. "
                            "Проверьте доступные слоты и выберите другое время или корт."
                        ) % old_court_name,
                    }
                }
    
    @api.onchange("date", "start_time", "duration", "sport_center_id")
    def _onchange_time_slot(self):
        """Проверка доступности времени и рабочих часов при изменении времени"""
        if not all([self.date, self.start_time is not None, self.duration]):
            # Если время не полностью заполнено, сбрасываем корт (если он был выбран)
            if self.tennis_court_id:
                self.tennis_court_id = False
            return
        
        # Пропускаем проверку, если время равно 0.0 (дефолтное значение) - пользователь еще не выбрал время
        if self.start_time == 0.0:
            return
        
        # Проверка на прошлое время (только если время реально выбрано пользователем)
        start_datetime = fields.Datetime.to_datetime(self.date)
        start_hour = int(self.start_time)
        start_minute = int((self.start_time - start_hour) * 60)
        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)
        end_datetime = start_datetime + timedelta(hours=self.duration)
        
        # Проверяем, что время не в прошлом
        now = fields.Datetime.now()
        if start_datetime < now:
            # Сбрасываем время и корт, если время в прошлом
            self.start_time = 0.0
            if self.tennis_court_id:
                self.tennis_court_id = False
            return {
                "warning": {
                    "title": _("Время в прошлом"),
                    "message": _(
                        "Нельзя создать тренировку в прошлом. "
                        "Выбранное время: %s. "
                        "Текущее время: %s. "
                        "Пожалуйста, выберите время в будущем."
                    ) % (
                        start_datetime.strftime("%d.%m.%Y %H:%M"),
                        now.strftime("%d.%m.%Y %H:%M"),
                    ),
                }
            }
        
        # Если корт уже выбран, проверяем соответствие
        if not self.tennis_court_id or not self.sport_center_id:
            return
        
        # Проверка рабочих часов центра
        center = self.sport_center_id
        start_hour_float = start_hour + start_minute / 60.0
        end_hour_float = start_hour_float + self.duration
        
        if start_hour_float < center.work_time_start or end_hour_float > center.work_time_end:
            # Сбрасываем корт, если время не соответствует рабочим часам
            self.tennis_court_id = False
            return {
                "warning": {
                    "title": _("Вне рабочих часов"),
                    "message": _(
                        "Выбранное время не соответствует рабочим часам центра '%s' "
                        "(с %.1f до %.1f часов). "
                        "Выбранное время: %.1f - %.1f часов. "
                        "Пожалуйста, выберите время в пределах рабочих часов."
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
            # Сбрасываем корт, если он занят
            old_court_name = self.tennis_court_id.name
            self.tennis_court_id = False
            return {
                "warning": {
                    "title": _("Время занято"),
                    "message": _(
                        "Корт '%s' уже занят в это время. "
                        "Проверьте доступные слоты и выберите другое время или корт."
                    ) % old_court_name,
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
        
        # Получаем ID тренера заранее, используя sudo() для обхода правил доступа
        # Это нужно, чтобы избежать проверки доступа при чтении self.trainer_id
        trainer_id = self.trainer_id.id if self.trainer_id else False
        
        # Валидации - используем ID вместо объектов для избежания проверки доступа
        if not all([self.sport_center_id, self.tennis_court_id, trainer_id, 
                   self.training_type_id, self.date, self.start_time is not None, 
                   self.duration, self.client_ids]):
            raise ValidationError(_("Заполните все обязательные поля."))
        
        # Формируем datetime для начала
        start_datetime = fields.Datetime.to_datetime(self.date)
        start_hour = int(self.start_time)
        start_minute = int((self.start_time - start_hour) * 60)
        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)
        
        # Проверка на прошлое время
        now = fields.Datetime.now()
        if start_datetime < now:
            raise ValidationError(
                _(
                    "Нельзя создать тренировку в прошлом. "
                    "Выбранное время: %s. "
                    "Текущее время: %s. "
                    "Пожалуйста, выберите время в будущем."
                ) % (
                    start_datetime.strftime("%d.%m.%Y %H:%M"),
                    now.strftime("%d.%m.%Y %H:%M"),
                )
            )
        
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
        # Используем прямой поиск через final.center.trainer с sudo(), чтобы гарантировать проверку всех СЦ
        center_trainer_record = self.env["final.center.trainer"].sudo().search([
            ("employee_id", "=", trainer_id),
            ("sport_center_id", "=", self.sport_center_id.id),
        ], limit=1)
        if not center_trainer_record:
            # Используем sudo() для чтения имени тренера, чтобы обойти проблемы с доступом
            trainer_with_sudo = self.env["hr.employee"].sudo().browse(trainer_id)
            trainer_name = trainer_with_sudo.name if trainer_with_sudo.exists() else _("Неизвестный тренер")
            raise ValidationError(
                _("Тренер '%s' не привязан к спортивному центру '%s'.") %
                (trainer_name, self.sport_center_id.name)
            )
        
        # Проверка баланса клиентов (только для менеджера, т.к. тренер не видит баланс)
        user = self.env.user
        is_trainer = user.has_group("final.group_final_trainer")
        is_manager = user.has_group("final.group_final_manager")
        
        # Получаем цену за час для расчета стоимости
        price_per_hour = 0.0
        if self.sport_center_id and self.training_type_id:
            price_record = self.env["final.center.training.price"].search([
                ("center_id", "=", self.sport_center_id.id),
                ("training_type_id", "=", self.training_type_id.id),
            ], limit=1)
            if price_record:
                price_per_hour = price_record.price_per_hour
        
        # Рассчитываем стоимость для каждого клиента
        total_cost_per_client = price_per_hour * self.duration
        
        # Проверяем баланс клиентов (только для менеджера)
        if is_manager and total_cost_per_client > 0:
            insufficient_balance_clients = []
            for client in self.client_ids:
                if client.balance < total_cost_per_client:
                    insufficient_balance_clients.append(
                        f"{client.name} (баланс: {client.balance} {client.balance_currency_id.symbol if client.balance_currency_id else ''}, требуется: {total_cost_per_client} {client.balance_currency_id.symbol if client.balance_currency_id else ''})"
                    )
            
            if insufficient_balance_clients:
                raise ValidationError(
                    _(
                        "Недостаточно средств на балансе у следующих клиентов:\n%s\n"
                        "Пополните баланс перед созданием записи на тренировку."
                    )
                    % "\n".join(insufficient_balance_clients)
                )
        
        # Определяем статус в зависимости от роли пользователя
        if is_trainer:
            state = "pending_approval"  # Тренер создает - требуется апрув
        else:
            state = "confirmed"  # Менеджер создает - сразу подтверждено
        
        # Подготавливаем значения для создания записи
        booking_vals = {
            "sport_center_id": self.sport_center_id.id,
            "tennis_court_id": self.tennis_court_id.id,
            "trainer_id": trainer_id,  # Используем ID вместо self.trainer_id.id
            "training_type_id": self.training_type_id.id,
            "client_ids": [(6, 0, self.client_ids.ids)],
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "state": state,
            "created_by": user.id,
            "is_recurring": self.is_recurring,
        }
        
        # Если тренер создает запись, используем sudo() для обхода проверки доступа к hr.employee
        # Это необходимо, так как тренер не имеет доступа к записям других тренеров
        if is_trainer:
            booking = self.env["final.training.booking"].sudo().create(booking_vals)
        else:
            booking = self.env["final.training.booking"].create(booking_vals)
        
        # Отправляем уведомление менеджеру, если запись создана тренером
        if state == "pending_approval":
            booking._notify_manager_new_request()
        # Если запись сразу подтверждена (создал менеджер) — уведомляем клиентов
        elif state == "confirmed":
            booking._notify_clients_booking_created()
            # И сразу проверяем, не нужно ли отправить напоминание (если до начала уже < N часов)
            booking._maybe_send_reminder_immediately()
        
        # Если это повторяющаяся тренировка, создаем шаблон и связываем с booking
        if self.is_recurring and self.recurring_end_date and self.recurring_days_of_week:
            # Создаем шаблон повторяющейся тренировки
            recurring_vals = {
                "sport_center_id": self.sport_center_id.id,
                "tennis_court_id": self.tennis_court_id.id,
                "trainer_id": trainer_id,
                "training_type_id": self.training_type_id.id,
                "client_ids": [(6, 0, self.client_ids.ids)],
                "start_date": self.date,
                "end_date": self.recurring_end_date,
                "days_of_week": self.recurring_days_of_week,
                "time_start": self.start_time,
                "duration": self.duration,
                "frequency": "weekly",  # По умолчанию еженедельно
                "active": True,
                "approved": False,  # По умолчанию не одобрено
                "created_by": user.id,
            }
            
            # Если тренер создает шаблон, используем sudo() для обхода проверки доступа к hr.employee
            # Это необходимо, так как тренер не имеет доступа к записям других тренеров
            if is_trainer:
                recurring = self.env["final.training.recurring"].sudo().create(recurring_vals)
            else:
                recurring = self.env["final.training.recurring"].create(recurring_vals)
            
            # Связываем booking с шаблоном и помечаем как повторяющуюся
            booking.write({
                "recurring_id": recurring.id,
                "is_recurring": True,
            })
            
            # Если создал тренер, отправляем уведомление менеджеру
            if is_trainer:
                recurring._notify_manager_new_template()
        
        # Если тренер создал запись, возвращаем action для списка записей
        # Это необходимо, так как после создания с sudo() при попытке открыть форму
        # система пытается прочитать связанную запись hr.employee через поле trainer_id,
        # но у тренера может не быть доступа к этой записи из-за правил доступа
        if is_trainer:
            # Возвращаем action для списка записей тренера с фильтром по его ID
            # Тренер увидит свою созданную запись в списке
            return {
                "type": "ir.actions.act_window",
                "name": _("Тренировка создана"),
                "res_model": "final.training.booking",
                "view_mode": "list,form",  # В Odoo 18 используется "list" вместо "tree"
                "domain": [("trainer_id", "=", trainer_id)],
                "context": {
                    "search_default_trainer_id": trainer_id,
                    "default_trainer_id": trainer_id,
                    "create": False,  # Отключаем создание из списка
                },
                "target": "current",
            }
        else:
            # Для менеджера открываем форму созданной записи
            return {
                "type": "ir.actions.act_window",
                "name": _("Тренировка создана"),
                "res_model": "final.training.booking",
                "res_id": booking.id,
                "view_mode": "form",
                "target": "current",
            }

