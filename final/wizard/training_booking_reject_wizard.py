# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TrainingBookingRejectWizard(models.TransientModel):
    _name = "final.training.booking.reject.wizard"
    _description = "Мастер отклонения тренировки"

    booking_id = fields.Many2one(
        "final.training.booking",
        string="Тренировка",
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Text(
        string="Причина отклонения",
        help="Укажите причину отклонения тренировки",
    )

    @api.model
    def default_get(self, fields_list):
        """Устанавливает значения по умолчанию"""
        res = super().default_get(fields_list)
        if "default_booking_id" in self.env.context:
            res["booking_id"] = self.env.context["default_booking_id"]
        return res

    def action_reject_confirm(self):
        """Подтверждение отклонения"""
        self.ensure_one()
        if not self.booking_id:
            raise ValidationError(_("Не указана тренировка для отклонения."))
        
        # Вызываем метод отклонения на записи
        self.booking_id.action_reject_confirm(self.rejection_reason or "")
        
        return {
            "type": "ir.actions.act_window_close",
        }

