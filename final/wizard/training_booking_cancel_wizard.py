from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TrainingBookingCancelWizard(models.TransientModel):
    _name = "final.training.booking.cancel.wizard"
    _description = "Мастер запроса на отмену тренировки"

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
        for record in self:
            if record.booking_id:
                booking = record.booking_id.sudo()
                record.booking_name = booking.name or _("Тренировка")
            else:
                record.booking_name = ""
    cancel_reason = fields.Text(
        string="Причина отмены",
        help="Укажите причину отмены тренировки",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "default_booking_id" in self.env.context:
            res["booking_id"] = self.env.context["default_booking_id"]
        return res

    def action_request_cancel(self):
        self.ensure_one()
        if not self.booking_id:
            raise ValidationError(_("Не указана тренировка для отмены."))
        
        is_trainer = self.env.user.has_group("final.group_final_trainer")
        is_manager = self.env.user.has_group("final.group_final_manager")
        is_director = self.env.user.has_group("final.group_final_director")
        
        if not is_trainer or (is_manager or is_director):
            raise ValidationError(_("Этот wizard предназначен только для тренеров."))
        
        booking = self.booking_id.sudo()
        
        if booking.state in ("completed", "cancelled"):
            raise ValidationError(
                _("Нельзя отменить тренировку в статусе '%s'.") % booking._fields["state"]._description_string(self.env)
            )
        
        update_vals = {
            "cancel_requested": True,
            "cancel_requested_by": self.env.user.id,
            "cancel_requested_date": fields.Datetime.now(),
            "cancel_request_reason": self.cancel_reason or "",
        }
        
        if booking.state in ("confirmed", "draft"):
            update_vals["state"] = "pending_approval"
        
        booking.write(update_vals)
        
        booking._notify_manager_cancel_request()
        
        return {
            "type": "ir.actions.act_window_close",
        }

