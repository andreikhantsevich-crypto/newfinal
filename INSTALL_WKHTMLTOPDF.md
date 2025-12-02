# Инструкция по установке wkhtmltopdf для генерации PDF отчетов

## Проблема
Odoo требует установленный `wkhtmltopdf` для генерации PDF отчетов. Если он не установлен, отчеты будут показываться в HTML формате.

## Установка на Linux (Ubuntu/Debian)

```bash
# Обновляем список пакетов
sudo apt-get update

# Устанавливаем wkhtmltopdf
sudo apt-get install -y wkhtmltopdf

# Проверяем установку
wkhtmltopdf --version
```

## Установка на Linux (CentOS/RHEL)

```bash
# Устанавливаем зависимости
sudo yum install -y xorg-x11-fonts-75dpi xorg-x11-fonts-Type1

# Скачиваем и устанавливаем wkhtmltopdf
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox-0.12.6.1-2.centos8.x86_64.rpm
sudo rpm -ivh wkhtmltox-0.12.6.1-2.centos8.x86_64.rpm

# Проверяем установку
wkhtmltopdf --version
```

## Альтернатива: Использование WeasyPrint (Odoo 18)

В Odoo 18 может использоваться WeasyPrint вместо wkhtmltopdf. Для его использования нужно:

1. Установить системные зависимости:
```bash
sudo apt-get install -y python3-weasyprint
```

2. В настройках Odoo (Settings > Technical > Parameters > System Parameters) можно установить:
   - Ключ: `report.url`
   - Значение: URL вашего Odoo сервера

## Проверка установки в Odoo

После установки перезапустите Odoo и попробуйте снова сгенерировать PDF отчет.

## Дополнительная информация

- Официальный сайт: http://wkhtmltopdf.org/
- Документация Odoo: https://www.odoo.com/documentation/18.0/developer/reference/backend/reporting.html

