from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BalanceDepositWizard(models.TransientModel):
    _name = "final.balance.deposit.wizard"
    _description = "Мастер пополнения баланса клиента"

    partner_id = fields.Many2one(
        "res.partner",
        string="Клиент",
        required=True,
        domain="[('is_company', '=', False)]",
    )
    amount = fields.Monetary(
        string="Сумма пополнения",
        required=True,
        currency_field="currency_id",
        help="Сумма для пополнения баланса",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        related="partner_id.balance_currency_id",
        readonly=True,
    )
    current_balance = fields.Monetary(
        string="Текущий баланс",
        related="partner_id.balance",
        readonly=True,
        currency_field="currency_id",
    )
    new_balance = fields.Monetary(
        string="Баланс после пополнения",
        compute="_compute_new_balance",
        readonly=True,
        currency_field="currency_id",
    )
    description = fields.Text(
        string="Описание",
        help="Дополнительное описание транзакции",
    )

    @api.depends("amount", "current_balance")
    def _compute_new_balance(self):
        for record in self:
            record.new_balance = record.current_balance + record.amount

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Если клиент передан в контексте
        if "default_partner_id" in self.env.context:
            res["partner_id"] = self.env.context["default_partner_id"]
        
        return res

    @api.constrains("amount")
    def _check_amount_positive(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(
                    _("Сумма пополнения должна быть положительным числом.")
                )

    def action_deposit(self):
        self.ensure_one()
        
        if not self.partner_id:
            raise ValidationError(_("Выберите клиента."))
        
        if self.amount <= 0:
            raise ValidationError(_("Сумма пополнения должна быть положительным числом."))
        
        description = self.description or _("Пополнение баланса")
        self.partner_id.deposit_balance(self.amount, description)
        return {
            "type": "ir.actions.act_window_close",
        }

