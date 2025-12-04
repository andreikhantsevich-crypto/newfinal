from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TrainingBookingRejectRescheduleWizard(models.TransientModel):
    _name = "final.training.booking.reject.reschedule.wizard"
    _description = "Мастер отклонения запроса на перенос тренировки"

    booking_id = fields.Many2one(
        "final.training.booking",
        string="Тренировка",
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Text(
        string="Причина отклонения",
        help="Укажите причину отклонения запроса на перенос",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "default_booking_id" in self.env.context:
            res["booking_id"] = self.env.context["default_booking_id"]
        return res

    def action_reject_confirm(self):
        self.ensure_one()
        if not self.booking_id:
            raise ValidationError(_("Не указана тренировка для отклонения."))
        
        self.booking_id.action_reject_reschedule_confirm(self.rejection_reason or "")
        
        return {
            "type": "ir.actions.act_window_close",
        }

