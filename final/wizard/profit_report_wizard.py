from datetime import timedelta

from odoo import _, api, fields, models


class FinalProfitReportWizard(models.TransientModel):
    _name = "final.profit.report.wizard"
    _description = "Wizard для PDF отчета по прибыли в разрезе СЦ"

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
        required=True,
        help="Выберите один или несколько спортивных центров для отчета.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Валюта",
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )

    def action_print_pdf(self):
        """Генерирует PDF отчет по прибыли в разрезе СЦ и скачивает его."""
        self.ensure_one()
        report = self.env.ref('final.action_report_profit_by_centers')
        # Используем стандартный метод report_action
        action = report.report_action(self, config=False)
        # Добавляем параметр для автоматического скачивания через URL
        # В Odoo для скачивания PDF добавляем параметр download=1 в контекст
        if isinstance(action, dict):
            # Изменяем target на download для автоматического скачивания
            action['target'] = 'download'
            # Также можно модифицировать URL если он есть
            if 'url' in action and 'download' not in action['url']:
                separator = '&' if '?' in action['url'] else '?'
                action['url'] = f"{action['url']}{separator}download=1"
        return action

    def _get_profit_data(self):
        """Получает данные о прибыли для отчета."""
        self.ensure_one()
        
        # Подготовка домена по датам и СЦ
        domain = [("state", "=", "completed")]
        
        if self.date_from:
            date_from_dt = fields.Datetime.to_datetime(self.date_from)
            domain.append(("start_datetime", ">=", date_from_dt))
        
        if self.date_to:
            date_to_dt = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
            domain.append(("start_datetime", "<", date_to_dt))
        
        if self.center_ids:
            domain.append(("sport_center_id", "in", self.center_ids.ids))
        
        # Получаем все завершенные тренировки
        Booking = self.env["final.training.booking"].sudo()
        bookings = Booking.search(domain, order="sport_center_id, start_datetime")
        
        # Группируем данные по СЦ
        centers_data = {}
        total_profit = 0.0
        total_bookings = 0
        
        for booking in bookings:
            center_id = booking.sport_center_id.id
            center_name = booking.sport_center_id.name
            
            if center_id not in centers_data:
                centers_data[center_id] = {
                    'name': center_name,
                    'profit': 0.0,
                    'bookings_count': 0,
                    'bookings': [],
                }
            
            profit = booking.profit_amount or 0.0
            centers_data[center_id]['profit'] += profit
            centers_data[center_id]['bookings_count'] += 1
            centers_data[center_id]['bookings'].append({
                'id': booking.id,
                'date': booking.start_datetime.date() if booking.start_datetime else False,
                'trainer': booking.trainer_id.name if booking.trainer_id else '',
                'training_type': booking.training_type_id.name if booking.training_type_id else '',
                'price': booking.total_price or 0.0,
                'trainer_rate': booking.trainer_rate_amount or 0.0,
                'profit': profit,
            })
            
            total_profit += profit
            total_bookings += 1
        
        return {
            'centers': list(centers_data.values()),
            'total_profit': total_profit,
            'total_bookings': total_bookings,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'currency': self.currency_id,
        }
