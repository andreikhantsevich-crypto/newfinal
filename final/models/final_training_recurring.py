# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import calendar


class FinalTrainingRecurring(models.Model):
    _name = "final.training.recurring"
    _description = "Повторяющаяся тренировка"
    _order = "start_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Название",
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
        index=True,
        check_company=False,
    )
    training_type_id = fields.Many2one(
        "final.training.type",
        string="Тип тренировки",
        required=True,
        ondelete="restrict",
    )
    client_ids = fields.Many2many(
        "res.partner",
        "final_training_recurring_partner_rel",
        "recurring_id",
        "partner_id",
        string="Клиенты",
        required=True,
        domain="[('is_company', '=', False)]",
    )
    start_date = fields.Date(
        string="Дата начала",
        required=True,
        index=True,
        help="Дата начала повторяющихся тренировок",
    )
    end_date = fields.Date(
        string="Дата окончания",
        required=True,
        index=True,
        help="Дата окончания повторяющихся тренировок",
    )
    days_of_week = fields.Char(
        string="Дни недели",
        required=True,
        help="Дни недели через запятую (0=Понедельник, 1=Вторник, ..., 6=Воскресенье). Например: 0,2,4",
    )
    time_start = fields.Float(
        string="Время начала (часы)",
        required=True,
        help="Время начала в формате часов (например, 14.5 = 14:30)",
    )
    duration = fields.Float(
        string="Продолжительность (часов)",
        required=True,
        default=1.0,
        help="Продолжительность тренировки в часах",
    )
    frequency = fields.Selection(
        selection=[
            ("weekly", "Еженедельно"),
            ("biweekly", "Раз в 2 недели"),
        ],
        string="Частота",
        default="weekly",
        required=True,
        help="Частота повторения тренировок",
    )
    booking_ids = fields.One2many(
        "final.training.booking",
        "recurring_id",
        string="Сгенерированные тренировки",
        help="Тренировки, созданные на основе этого шаблона",
    )
    active = fields.Boolean(
        string="Активно",
        default=True,
        help="Если неактивно, новые тренировки не будут генерироваться",
    )
    approved = fields.Boolean(
        string="Одобрено",
        default=False,
        help="Если одобрено, тренировки будут создаваться со статусом 'Подтверждена', иначе 'На одобрении'",
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
    created_by = fields.Many2one(
        "res.users",
        string="Создал",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
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

    _sql_constraints = [
        (
            "final_training_recurring_date_check",
            "CHECK(start_date <= end_date)",
            "Дата начала должна предшествовать дате окончания.",
        ),
        (
            "final_training_recurring_duration_min",
            "CHECK(duration >= 1)",
            "Минимальная продолжительность тренировки - 1 час.",
        ),
    ]

    @api.depends("trainer_id", "sport_center_id", "training_type_id", "start_date", "days_of_week")
    def _compute_name(self):
        """Генерация названия повторяющейся тренировки"""
        for record in self:
            if not record.start_date:
                record.name = _("Новая повторяющаяся тренировка")
                continue
            
            # Тип тренировки
            type_name = record.training_type_id.name if record.training_type_id else ""
            
            # Тренер - используем sudo() для доступа к имени тренера, если нет прав
            try:
                trainer_name = record.trainer_id.name if record.trainer_id else ""
            except:
                # Если нет доступа к trainer_id, используем sudo()
                trainer_name = record.sudo().trainer_id.name if record.trainer_id else ""
            
            # Дни недели
            days_str = ""
            if record.days_of_week:
                day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                try:
                    days = [int(d.strip()) for d in record.days_of_week.split(",") if d.strip()]
                    days_str = ", ".join([day_names[d] for d in days if 0 <= d <= 6])
                except:
                    days_str = record.days_of_week
            
            # Форматируем дату
            date_str = record.start_date.strftime("%d.%m.%Y") if record.start_date else ""
            
            name_parts = []
            if type_name:
                name_parts.append(type_name)
            if trainer_name:
                name_parts.append(f"({trainer_name})")
            if days_str:
                name_parts.append(f"[{days_str}]")
            if date_str:
                name_parts.append(f"с {date_str}")
            
            record.name = " ".join(name_parts) if name_parts else _("Повторяющаяся тренировка")

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        """Проверка диапазона дат"""
        for record in self:
            if record.start_date and record.end_date:
                if record.start_date > record.end_date:
                    raise ValidationError(
                        _("Дата начала должна предшествовать дате окончания.")
                    )

    @api.constrains("days_of_week")
    def _check_days_of_week(self):
        """Проверка формата дней недели"""
        for record in self:
            if not record.days_of_week:
                continue
            
            try:
                days = [int(d.strip()) for d in record.days_of_week.split(",") if d.strip()]
                for day in days:
                    if day < 0 or day > 6:
                        raise ValidationError(
                            _("Дни недели должны быть числами от 0 (Понедельник) до 6 (Воскресенье).")
                        )
            except ValueError:
                raise ValidationError(
                    _("Неверный формат дней недели. Используйте числа через запятую (0-6).")
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

    @api.constrains("duration")
    def _check_duration_step(self):
        """Проверка что продолжительность кратна 1 часу"""
        for record in self:
            if record.duration > 0:
                if abs(record.duration - round(record.duration)) > 0.01:
                    raise ValidationError(
                        _("Продолжительность тренировки должна быть кратной 1 часу (1, 2, 3... часов).")
                    )

    def _parse_days_of_week(self):
        """Парсит строку дней недели в список чисел"""
        if not self.days_of_week:
            return []
        
        try:
            return [int(d.strip()) for d in self.days_of_week.split(",") if d.strip()]
        except:
            return []

    def _get_dates_for_generation(self, start_date=None, end_date=None):
        """Возвращает список дат для генерации тренировок"""
        self.ensure_one()
        
        if not start_date:
            start_date = self.start_date
        if not end_date:
            end_date = self.end_date
        
        if not start_date or not end_date:
            return []
        
        dates = []
        days_of_week = self._parse_days_of_week()
        
        if not days_of_week:
            return []
        
        current_date = start_date
        # Вычисляем номер недели от начала года для определения четности
        start_week_num = start_date.isocalendar()[1]
        
        while current_date <= end_date:
            current_weekday = current_date.weekday()  # 0=Monday, 6=Sunday
            
            if current_weekday in days_of_week:
                # Проверяем частоту
                if self.frequency == "weekly":
                    # Еженедельно - добавляем все подходящие дни
                    dates.append(current_date)
                elif self.frequency == "biweekly":
                    # Раз в 2 недели - проверяем четность недели
                    current_week_num = current_date.isocalendar()[1]
                    week_diff = current_week_num - start_week_num
                    if week_diff % 2 == 0:
                        dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        return dates

    def generate_bookings(self, start_date=None, end_date=None):
        """Генерирует записи на тренировки на основе параметров"""
        self.ensure_one()
        
        if not self.active:
            raise ValidationError(_("Нельзя генерировать тренировки для неактивного шаблона."))
        
        # Определяем диапазон дат
        if not start_date:
            start_date = self.start_date
        if not end_date:
            end_date = self.end_date
        
        if not start_date or not end_date:
            raise ValidationError(_("Укажите даты начала и окончания для генерации тренировок."))
        
        # Получаем список дат для генерации
        dates = self._get_dates_for_generation(start_date, end_date)
        
        if not dates:
            raise ValidationError(
                _("Не найдено дат для генерации тренировок в указанном диапазоне.")
            )
        
        # Определяем статус в зависимости от одобрения шаблона
        # Если шаблон одобрен менеджером, тренировки создаются сразу подтвержденными
        # Если не одобрен, то в зависимости от роли создателя
        user = self.env.user
        is_trainer = user.has_group("final.group_final_trainer")
        if self.approved:
            state = "confirmed"
        else:
            if is_trainer:
                state = "pending_approval"
            else:
                state = "confirmed"
        
        # Генерируем тренировки
        created_bookings = []
        skipped_bookings = []
        
        for date in dates:
            # Формируем datetime для начала
            start_hour = int(self.time_start)
            start_minute = int((self.time_start - start_hour) * 60)
            start_datetime = datetime.combine(date, datetime.min.time()).replace(
                hour=start_hour, minute=start_minute, second=0
            )
            
            # Формируем datetime для окончания
            end_datetime = start_datetime + timedelta(hours=self.duration)
            
            # Проверяем пересечение с существующими записями
            overlapping = self.env["final.training.booking"].search([
                ("tennis_court_id", "=", self.tennis_court_id.id),
                ("state", "in", ["confirmed", "pending_approval", "draft"]),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ], limit=1)
            
            # Проверяем, не создана ли уже тренировка на эту дату из этого шаблона
            existing = self.env["final.training.booking"].search([
                ("recurring_id", "=", self.id),
                ("start_datetime", "=", start_datetime),
            ], limit=1)
            
            if existing:
                skipped_bookings.append(f"{date.strftime('%d.%m.%Y')} - уже существует")
                continue
            
            if overlapping:
                skipped_bookings.append(f"{date.strftime('%d.%m.%Y')} - корт занят")
                continue
            
            # Проверяем рабочие часы центра
            center = self.sport_center_id
            start_hour_float = start_hour + start_minute / 60.0
            end_hour_float = start_hour_float + self.duration
            
            if start_hour_float < center.work_time_start or end_hour_float > center.work_time_end:
                skipped_bookings.append(f"{date.strftime('%d.%m.%Y')} - вне рабочих часов")
                continue
            
            # Создаем запись
            try:
                booking_vals = {
                    "sport_center_id": self.sport_center_id.id,
                    "tennis_court_id": self.tennis_court_id.id,
                    "trainer_id": self.trainer_id.id,
                    "training_type_id": self.training_type_id.id,
                    "client_ids": [(6, 0, self.client_ids.ids)],
                    "start_datetime": start_datetime,
                    "end_datetime": end_datetime,
                    "state": state,
                    "created_by": user.id,
                    "recurring_id": self.id,
                    "is_recurring": True,
                }
                
                # Если тренер генерирует тренировки, используем sudo() для обхода проверки доступа к hr.employee
                # Это необходимо, так как тренер не имеет доступа к записям других тренеров
                if is_trainer:
                    booking = self.env["final.training.booking"].sudo().create(booking_vals)
                else:
                    booking = self.env["final.training.booking"].create(booking_vals)
                created_bookings.append(booking)
                
                # Отправляем уведомление менеджеру, если создано тренером и шаблон не одобрен
                if state == "pending_approval" and not self.approved:
                    booking._notify_manager_new_request()
            
            except Exception as e:
                skipped_bookings.append(f"{date.strftime('%d.%m.%Y')} - ошибка: {str(e)}")
                continue
        
        # Формируем сообщение о результате
        message_parts = []
        if created_bookings:
            message_parts.append(_("Создано тренировок: %d") % len(created_bookings))
        if skipped_bookings:
            message_parts.append(_("Пропущено: %d") % len(skipped_bookings))
            if len(skipped_bookings) <= 10:
                message_parts.append("\n" + "\n".join(skipped_bookings))
        
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Генерация завершена"),
                "message": "\n".join(message_parts) if message_parts else _("Тренировки не созданы"),
                "type": "success" if created_bookings else "warning",
                "sticky": len(skipped_bookings) > 0,
            },
        }

    def action_generate_bookings(self):
        """Действие для генерации тренировок (кнопка в форме)"""
        self.ensure_one()
        return self.generate_bookings()
    
    def action_approve(self):
        """Одобрение шаблона повторяющейся тренировки менеджером"""
        self.ensure_one()
        
        # Проверка прав - только менеджер или директор
        if not self.env.user.has_group("final.group_final_manager") and not self.env.user.has_group("final.group_final_director"):
            raise ValidationError(_("Только менеджер или директор могут одобрять шаблоны повторяющихся тренировок."))
        
        # Проверка баланса клиентов перед одобрением
        # Рассчитываем сумму списания для каждого клиента
        # Нужно получить цену за час для расчета
        price_per_hour = 0.0
        if self.sport_center_id and self.training_type_id:
            price_record = self.env["final.center.training.price"].search([
                ("center_id", "=", self.sport_center_id.id),
                ("training_type_id", "=", self.training_type_id.id),
            ], limit=1)
            if price_record:
                price_per_hour = price_record.price_per_hour
        
        amount_per_client = price_per_hour * self.duration
        
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
                        "Нельзя одобрить шаблон: недостаточно средств на балансе у следующих клиентов:\n%s\n"
                        "Пополните баланс клиентов перед одобрением шаблона."
                    )
                    % "\n".join(insufficient_balance_clients)
                )
        
        self.write({
            "approved": True,
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })
        
        return True
    
    def read(self, fields=None, load='_classic_read'):
        """Переопределяем read для обхода проблем с доступом к trainer_id"""
        # Если пользователь не имеет доступа к trainer_id, используем sudo() для чтения
        # Это необходимо, так как тренер не имеет доступа к записям других тренеров в hr.employee
        try:
            # Пытаемся прочитать обычным способом
            result = super().read(fields=fields, load=load)
            # Проверяем, нет ли _unknown объектов в результате
            for record_data in result:
                if isinstance(record_data, dict):
                    for field_name, field_value in record_data.items():
                        # Если поле Many2one вернуло _unknown, заменяем на False
                        if hasattr(field_value, '__class__') and field_value.__class__.__name__ == '_unknown':
                            record_data[field_name] = False
            return result
        except (AttributeError, Exception) as e:
            # Если возникла ошибка доступа (например, с _unknown объектами), используем sudo()
            # Важно: вызываем super() напрямую с sudo(), чтобы избежать рекурсии
            try:
                return super(FinalTrainingRecurring, self.sudo()).read(fields=fields, load=load)
            except Exception:
                # Если и с sudo() не получилось, возвращаем базовый результат
                return super().read(fields=fields, load=load)
    
    def _notify_manager_new_template(self):
        """Отправка уведомления менеджеру о новом шаблоне повторяющейся тренировки"""
        if not self.sport_center_id or not self.sport_center_id.manager_id or not self.sport_center_id.manager_id.user_id:
            return
        
        # Используем sudo() для доступа к имени тренера, если нет прав
        try:
            trainer_name = self.trainer_id.name if self.trainer_id else _("Не указан")
        except:
            trainer_name = self.sudo().trainer_id.name if self.trainer_id else _("Не указан")
        
        self.env["mail.message"].create({
            "model": "final.training.recurring",
            "res_id": self.id,
            "message_type": "notification",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "subject": _("Новый шаблон повторяющейся тренировки"),
            "body": _(
                "Тренер %s создал шаблон повторяющейся тренировки '%s'. "
                "Требуется ваше одобрение в разделе 'Повторяющиеся тренировки'."
            ) % (
                trainer_name,
                self.name or _("Тренировка"),
            ),
            "partner_ids": [(4, self.sport_center_id.manager_id.user_id.partner_id.id)],
        })

