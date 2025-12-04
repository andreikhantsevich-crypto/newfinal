from datetime import timedelta

from odoo import _, api, fields, models


class FinalStatisticsReportWizard(models.TransientModel):
    _name = "final.statistics.report.wizard"
    _description = "Отчеты по тренерам, видам тренировок и клиентам"

    date_from = fields.Date(
        string="Дата с",
        default=lambda self: fields.Date.to_date(
            fields.Date.today().replace(day=1)
        ),
        required=True,
    )
    date_to = fields.Date(
        string="Дата по",
        default=fields.Date.today,
        required=True,
    )
    center_ids = fields.Many2many(
        "final.sport.center",
        string="Спортивные центры",
        help="Оставьте пустым, чтобы учитывать все центры.",
    )

    most_profitable_trainer_id = fields.Many2one(
        "hr.employee",
        string="Самый прибыльный тренер",
        readonly=True,
    )
    most_profitable_trainer_profit = fields.Monetary(
        string="Прибыль тренера",
        readonly=True,
        currency_field="currency_id",
    )

    most_popular_training_type_id = fields.Many2one(
        "final.training.type",
        string="Самый посещаемый вид тренировки",
        readonly=True,
    )
    most_popular_training_type_count = fields.Integer(
        string="Количество тренировок (по виду)",
        readonly=True,
    )

    most_active_client_id = fields.Many2one(
        "res.partner",
        string="Самый активный клиент",
        readonly=True,
    )
    most_active_client_count = fields.Integer(
        string="Количество тренировок (по клиенту)",
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )

    @api.onchange("date_from", "date_to", "center_ids")
    def _onchange_compute_statistics(self):
        for wizard in self:
            wizard._compute_statistics()

    def action_compute_statistics(self):
        self._compute_statistics()
        return False

    def _compute_statistics(self):
        self.ensure_one()

        domain = [("state", "=", "completed")]

        if self.date_from:
            date_from_dt = fields.Datetime.to_datetime(self.date_from)
            domain.append(("start_datetime", ">=", date_from_dt))

        if self.date_to:
            date_to_dt = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
            domain.append(("start_datetime", "<", date_to_dt))

        if self.center_ids:
            domain.append(("sport_center_id", "in", self.center_ids.ids))

        Booking = self.env["final.training.booking"].sudo()
        bookings = Booking.search(domain)

        trainer_profit = {}
        for b in bookings:
            if not b.trainer_id:
                continue
            trainer_profit[b.trainer_id.id] = trainer_profit.get(b.trainer_id.id, 0.0) + (
                b.profit_amount or 0.0
            )

        if trainer_profit:
            best_trainer_id = max(trainer_profit, key=trainer_profit.get)
            self.most_profitable_trainer_id = self.env["hr.employee"].browse(
                best_trainer_id
            )
            self.most_profitable_trainer_profit = trainer_profit[best_trainer_id]
        else:
            self.most_profitable_trainer_id = False
            self.most_profitable_trainer_profit = 0.0

        type_counts = {}
        for b in bookings:
            if not b.training_type_id:
                continue
            type_counts[b.training_type_id.id] = type_counts.get(
                b.training_type_id.id, 0
            ) + 1

        if type_counts:
            best_type_id = max(type_counts, key=type_counts.get)
            self.most_popular_training_type_id = self.env[
                "final.training.type"
            ].browse(best_type_id)
            self.most_popular_training_type_count = type_counts[best_type_id]
        else:
            self.most_popular_training_type_id = False
            self.most_popular_training_type_count = 0

        client_counts = {}
        for b in bookings:
            for client in b.client_ids:
                # Учитываем только "наших" реальных клиентов:
                # - физлицо
                # - с привязанным Telegram User ID (менеджер заполняет вручную)
                if client.is_company or not client.telegram_user_id:
                    continue
                client_counts[client.id] = client_counts.get(client.id, 0) + 1

        if client_counts:
            best_client_id = max(client_counts, key=client_counts.get)
            self.most_active_client_id = self.env["res.partner"].browse(best_client_id)
            self.most_active_client_count = client_counts[best_client_id]
        else:
            self.most_active_client_id = False
            self.most_active_client_count = 0

        return True


