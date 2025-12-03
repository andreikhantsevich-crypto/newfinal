# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class TrainingBookingRescheduleWizard(models.TransientModel):
    _name = "final.training.booking.reschedule.wizard"
    _description = "Мастер переноса тренировки"

    booking_id = fields.Many2one(
        "final.training.booking",
        string="Тренировка",
        required=True,
        readonly=True,
    )
    booking_name = fields.Char(
        string="Тренировка",
        compute="_compute_booking_name",
        store=False,
        help="Название тренировки для безопасного отображения",
    )
    
    @api.depends("booking_id")
    def _compute_booking_name(self):
        """Вычисляет название тренировки с использованием sudo() для обхода правил доступа"""
        for record in self:
            if record.booking_id:
                # Используем sudo() для чтения booking, чтобы обойти правила доступа к trainer_id
                booking = record.booking_id.sudo()
                record.booking_name = booking.name or _("Тренировка")
            else:
                record.booking_name = ""
    is_trainer = fields.Boolean(
        string="Инициировано тренером",
        default=False,
        readonly=True,
    )
    sport_center_id = fields.Many2one(
        "final.sport.center",
        string="Спортивный центр",
        related="booking_id.sport_center_id",
        readonly=True,
    )
    date = fields.Date(
        string="Новая дата",
        required=True,
        help="Новая дата тренировки",
    )
    start_time = fields.Float(
        string="Новое время начала",
        required=True,
        help="Время начала в формате часов (например, 14.5 = 14:30)",
    )
    duration = fields.Float(
        string="Продолжительность (часов)",
        required=True,
        help="Продолжительность тренировки в часах (минимум 1 час, шаг 1 час)",
    )
    tennis_court_id = fields.Many2one(
        "final.tennis.court",
        string="Новый корт (опционально)",
        domain="[('sport_center_id', '=', sport_center_id)]",
        help="Оставьте пустым, если корт не меняется",
    )
    reschedule_reason = fields.Text(
        string="Причина переноса",
        help="Укажите причину переноса тренировки",
    )

    @api.model
    def default_get(self, fields_list):
        """Устанавливает значения по умолчанию"""
        res = super().default_get(fields_list)
        if "default_booking_id" in self.env.context:
            booking_id = self.env.context["default_booking_id"]
            # Используем sudo() для чтения booking, чтобы обойти правила доступа к trainer_id
            booking = self.env["final.training.booking"].sudo().browse(booking_id)
            res["booking_id"] = booking_id
            
            # Устанавливаем текущие значения тренировки
            if booking.exists():
                if booking.start_datetime:
                    res["date"] = booking.start_datetime.date()
                    start_hour = booking.start_datetime.hour
                    start_minute = booking.start_datetime.minute
                    res["start_time"] = start_hour + start_minute / 60.0
                res["duration"] = booking.duration_hours or 1.0
                res["tennis_court_id"] = booking.tennis_court_id.id
        
        if "default_is_trainer" in self.env.context:
            res["is_trainer"] = self.env.context["default_is_trainer"]
        
        return res

    @api.onchange("date", "start_time", "duration", "tennis_court_id")
    def _onchange_time_slot(self):
        """Проверка доступности времени при изменении"""
        if not all([self.date, self.start_time is not None, self.duration]):
            return
        
        # Пропускаем проверку, если время равно 0.0 (дефолтное значение)
        if self.start_time == 0.0:
            return
        
        # Проверка на прошлое время
        start_datetime = fields.Datetime.to_datetime(self.date)
        start_hour = int(self.start_time)
        start_minute = int((self.start_time - start_hour) * 60)
        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)
        end_datetime = start_datetime + timedelta(hours=self.duration)
        
        # Проверяем, что время не в прошлом
        now = fields.Datetime.now()
        if start_datetime < now:
            return {
                "warning": {
                    "title": _("Время в прошлом"),
                    "message": _("Нельзя перенести тренировку на время в прошлом."),
                }
            }
        
        # Проверяем рабочие часы центра
        if self.sport_center_id:
            start_hour_float = start_hour + start_minute / 60.0
            end_hour_float = start_hour_float + self.duration
            
            if start_hour_float < self.sport_center_id.work_time_start or end_hour_float > self.sport_center_id.work_time_end:
                return {
                    "warning": {
                        "title": _("Вне рабочих часов"),
                        "message": _(
                            "Тренировка должна быть в рабочие часы центра "
                            "(с %.1f до %.1f часов)."
                        ) % (self.sport_center_id.work_time_start, self.sport_center_id.work_time_end),
                    }
                }
        
        # Используем sudo() для чтения booking, чтобы обойти правила доступа к trainer_id
        booking = self.booking_id.sudo()
        
        # Проверяем занятость корта (если выбран новый корт или корт не меняется)
        court_id = self.tennis_court_id.id if self.tennis_court_id else booking.tennis_court_id.id
        
        if court_id:
            # Ищем пересечения с другими записями на том же корте
            overlapping = self.env["final.training.booking"].search([
                ("tennis_court_id", "=", court_id),
                ("id", "!=", booking.id),
                ("state", "in", ["confirmed", "pending_approval", "draft"]),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ], limit=1)
            
            if overlapping:
                court_name = self.tennis_court_id.name if self.tennis_court_id else booking.tennis_court_id.name
                return {
                    "warning": {
                        "title": _("Время занято"),
                        "message": _(
                            "Корт '%s' уже занят в это время. "
                            "Проверьте доступные слоты и выберите другое время или корт."
                        ) % court_name,
                    }
                }
        
        # Проверяем занятость тренера
        trainer_id = booking.trainer_id.id if booking.trainer_id else False
        if trainer_id:
            overlapping = self.env["final.training.booking"].search([
                ("trainer_id", "=", trainer_id),
                ("id", "!=", booking.id),
                ("state", "in", ["draft", "pending_approval", "confirmed"]),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ], limit=1)
            
            if overlapping:
                trainer_name = booking.trainer_id.name if booking.trainer_id else _("Не указан")
                return {
                    "warning": {
                        "title": _("Тренер занят"),
                        "message": _(
                            "Тренер '%s' уже занят другой тренировкой в это время. "
                            "Выберите другое время."
                        ) % trainer_name,
                    }
                }

    @api.constrains("duration")
    def _check_duration(self):
        """Проверка продолжительности"""
        for record in self:
            if record.duration < 1.0:
                raise ValidationError(_("Минимальная продолжительность тренировки - 1 час."))
            if abs(record.duration - round(record.duration)) > 0.01:
                raise ValidationError(_("Продолжительность должна быть кратной 1 часу (1, 2, 3... часов)."))

    def action_request_reschedule(self):
        """Создание запроса на перенос"""
        self.ensure_one()
        if not self.booking_id:
            raise ValidationError(_("Не указана тренировка для переноса."))
        
        # Используем sudo() для чтения booking, чтобы обойти правила доступа к trainer_id
        booking = self.booking_id.sudo()
        
        # Проверяем, что тренировка в статусе, который можно перенести
        if booking.state in ("completed", "cancelled"):
            raise ValidationError(
                _("Нельзя перенести тренировку в статусе '%s'.") % booking._fields["state"]._description_string(self.env)
            )
        
        # Формируем новое время
        start_hour = int(self.start_time)
        start_minute = int((self.start_time - start_hour) * 60)
        start_datetime = fields.Datetime.to_datetime(self.date)
        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)
        end_datetime = start_datetime + timedelta(hours=self.duration)
        
        # Проверяем, что время не в прошлом
        now = fields.Datetime.now()
        if start_datetime < now:
            raise ValidationError(_("Нельзя перенести тренировку на время в прошлом."))
        
        # Проверяем рабочие часы центра
        if self.sport_center_id:
            start_hour_float = start_hour + start_minute / 60.0
            end_hour_float = start_hour_float + self.duration
            
            if start_hour_float < self.sport_center_id.work_time_start or end_hour_float > self.sport_center_id.work_time_end:
                raise ValidationError(
                    _(
                        "Тренировка должна быть в рабочие часы центра '%s' "
                        "(с %.1f до %.1f часов)."
                    ) % (self.sport_center_id.name, self.sport_center_id.work_time_start, self.sport_center_id.work_time_end)
                )
        
        # Проверяем занятость корта
        court_id = self.tennis_court_id.id if self.tennis_court_id else booking.tennis_court_id.id
        
        if court_id:
            overlapping = self.env["final.training.booking"].search([
                ("tennis_court_id", "=", court_id),
                ("id", "!=", self.booking_id.id),
                ("state", "in", ["confirmed", "pending_approval", "draft"]),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ], limit=1)
            
            if overlapping:
                court_name = self.tennis_court_id.name if self.tennis_court_id else self.booking_id.tennis_court_id.name
                raise ValidationError(
                    _(
                        "Корт '%s' уже занят в это время другой тренировкой "
                        "(тренер: %s, время: %s - %s)."
                    ) % (
                        court_name,
                        overlapping.trainer_id.name if overlapping.trainer_id else _("Не указан"),
                        overlapping.start_datetime.strftime("%d.%m.%Y %H:%M") if overlapping.start_datetime else "",
                        overlapping.end_datetime.strftime("%H:%M") if overlapping.end_datetime else "",
                    )
                )
        
        # Проверяем занятость тренера
        trainer_id = booking.trainer_id.id if booking.trainer_id else False
        if trainer_id:
            overlapping = self.env["final.training.booking"].search([
                ("trainer_id", "=", trainer_id),
                ("id", "!=", booking.id),
                ("state", "in", ["draft", "pending_approval", "confirmed"]),
                ("start_datetime", "<", end_datetime),
                ("end_datetime", ">", start_datetime),
            ], limit=1)
            
            if overlapping:
                trainer_name = booking.trainer_id.name if booking.trainer_id else _("Не указан")
                raise ValidationError(
                    _(
                        "Тренер '%s' уже занят другой тренировкой в это время "
                        "(СЦ: %s, корт: %s, время: %s - %s)."
                    ) % (
                        trainer_name,
                        overlapping.sport_center_id.name or _("Не указан"),
                        overlapping.tennis_court_id.name or _("Не указан"),
                        overlapping.start_datetime.strftime("%d.%m.%Y %H:%M") if overlapping.start_datetime else "",
                        overlapping.end_datetime.strftime("%H:%M") if overlapping.end_datetime else "",
                    )
                )
        
        # Если тренер запрашивает перенос - создаем запрос на одобрение
        if self.is_trainer:
            # Подготавливаем значения для обновления
            update_vals = {
                "reschedule_requested": True,
                "reschedule_requested_by": self.env.user.id,
                "reschedule_requested_date": fields.Datetime.now(),
                "reschedule_new_start_datetime": start_datetime,
                "reschedule_new_end_datetime": end_datetime,
                "reschedule_new_court_id": self.tennis_court_id.id if self.tennis_court_id else False,
                "reschedule_reason": self.reschedule_reason or "",
            }
            
            # Если тренировка в статусе "confirmed" или "draft", переводим в "pending_approval"
            # чтобы менеджер видел её в списке запросов на одобрение
            if booking.state in ("confirmed", "draft"):
                update_vals["state"] = "pending_approval"
            
            booking.write(update_vals)
            
            # Отправляем уведомление менеджеру
            booking._notify_manager_reschedule_request()
        else:
            # Если менеджер/директор - переносим сразу
            update_vals = {
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            }
            
            if self.tennis_court_id:
                update_vals["tennis_court_id"] = self.tennis_court_id.id
            
            # Сбрасываем запрос на перенос, если он был
            if booking.reschedule_requested:
                update_vals.update({
                    "reschedule_requested": False,
                    "reschedule_requested_by": False,
                    "reschedule_requested_date": False,
                    "reschedule_new_start_datetime": False,
                    "reschedule_new_end_datetime": False,
                    "reschedule_new_court_id": False,
                    "reschedule_reason": False,
                })
            
            old_start = booking.start_datetime
            old_end = booking.end_datetime
            old_court = booking.tennis_court_id
            
            booking.write(update_vals)
            
            # Отправляем уведомления клиентам о переносе
            booking._notify_clients_booking_rescheduled(old_start, old_end, old_court)
        
        return {
            "type": "ir.actions.act_window_close",
        }

