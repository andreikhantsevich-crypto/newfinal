from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FinalBalanceTransaction(models.Model):
    _name = "final.balance.transaction"
    _description = "Транзакция баланса клиента"
    _order = "date desc, id desc"
    _rec_name = "display_name"

    partner_id = fields.Many2one(
        "res.partner",
        string="Клиент",
        required=True,
        ondelete="cascade",
        index=True,
    )
    transaction_type = fields.Selection(
        selection=[
            ("deposit", "Пополнение"),
            ("withdrawal", "Списание"),
        ],
        string="Тип транзакции",
        required=True,
        index=True,
    )
    amount = fields.Monetary(
        string="Сумма",
        required=True,
        currency_field="currency_id",
        help="Сумма транзакции (положительное число)",
    )
    booking_id = fields.Many2one(
        "final.training.booking",
        string="Тренировка",
        ondelete="set null",
        index=True,
        help="Связанная тренировка (для списаний)",
    )
    date = fields.Datetime(
        string="Дата и время",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    description = fields.Text(
        string="Описание",
        help="Дополнительное описание транзакции",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="partner_id.balance_currency_id",
        readonly=True,
        store=True,
    )
    display_name = fields.Char(
        string="Отображение",
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("partner_id", "transaction_type", "amount", "date")
    def _compute_display_name(self):
        for record in self:
            type_name = dict(record._fields["transaction_type"].selection).get(
                record.transaction_type, ""
            )
            date_str = (
                record.date.strftime("%d.%m.%Y %H:%M") if record.date else ""
            )
            record.display_name = f"{type_name} {record.amount} {record.currency_id.symbol if record.currency_id else ''} - {record.partner_id.name if record.partner_id else ''} ({date_str})"

    @api.constrains("amount")
    def _check_amount_positive(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(
                    _("Сумма транзакции должна быть положительным числом.")
                )

    def action_deposit(self, partner_id, amount, description=""):
        self.create(
            {
                "partner_id": partner_id,
                "transaction_type": "deposit",
                "amount": amount,
                "date": fields.Datetime.now(),
                "description": description,
            }
        )
        partner = self.env["res.partner"].sudo().browse(partner_id)
        partner.balance += amount

    def action_withdrawal(self, partner_id, amount, booking_id=None, description=""):
        partner = self.env["res.partner"].sudo().browse(partner_id)
        if partner.balance < amount:
            raise ValidationError(
                _(
                    "Недостаточно средств на балансе клиента '%s'. "
                    "Текущий баланс: %s %s, требуется: %s %s"
                )
                % (
                    partner.name,
                    partner.balance,
                    partner.balance_currency_id.symbol if partner.balance_currency_id else "",
                    amount,
                    partner.balance_currency_id.symbol if partner.balance_currency_id else "",
                )
            )
        
        self.create({
            "partner_id": partner_id,
            "transaction_type": "withdrawal",
            "amount": amount,
            "booking_id": booking_id,
            "date": fields.Datetime.now(),
            "description": description,
        })
        # Обновляем баланс клиента (используем sudo() для обхода прав доступа)
        partner.balance -= amount

