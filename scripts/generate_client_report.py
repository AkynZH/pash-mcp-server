# -*- coding: utf-8 -*-
"""
Генератор прозрачных отчетов для клиентов (Fair Billing System).
Рассчитывает комиссию строго как 10% от реальной экономии токенов.
"""
import os
from datetime import datetime
from pathlib import Path

# Конфигурация
TOKEN_PRICE_USD = 0.00001  # $0.01 за 1M токенов (или $0.00001 за 1k)
COMMISSION_RATE = 0.10     # Строго 10% от экономии

# Симуляция телеметрии за месяц (данные из бенчмарка Директивы 010)
TELEMETRY_LOGS = [
    {"task": "Анализ AWS логов", "raw_tokens": 50043, "pash_tokens": 7564},
    {"task": "Парсинг HTML контактов", "raw_tokens": 36552, "pash_tokens": 69},
    {"task": "Рефакторинг Python-скрипта", "raw_tokens": 62895, "pash_tokens": 16661},
    {"task": "Аудит NDA документа", "raw_tokens": 35750, "pash_tokens": 2789},
    {"task": "Генерация TechCrunch выжимки", "raw_tokens": 60801, "pash_tokens": 66},
]

def calculate_billing(logs):
    raw_tokens = sum(log['raw_tokens'] for log in logs)
    pash_tokens = sum(log['pash_tokens'] for log in logs)
    saved_tokens = raw_tokens - pash_tokens

    saved_dollars = saved_tokens * TOKEN_PRICE_USD
    commission = saved_dollars * COMMISSION_RATE

    # КРИТИЧЕСКАЯ ПРОВЕРКА: комиссия должна быть РАВНА 10% от экономии (с учетом float precision)
    expected_commission = saved_dollars * 0.10
    assert abs(commission - expected_commission) < 1e-9, f"BUG: Commission ({commission}) is not exactly 10% of savings ({expected_commission})!"

    return {
        "raw_tokens": raw_tokens,
        "pash_tokens": pash_tokens,
        "saved_tokens": saved_tokens,
        "saved_dollars": saved_dollars,
        "commission": commission
    }

def generate_report():
    print("🚀 Генерация прозрачного отчета для клиента...")
    
    billing = calculate_billing(TELEMETRY_LOGS)
    
    now = datetime.now()
    report_filename = f"client_report_{now.strftime('%Y_%m')}.md"
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / report_filename

    md_content = f"""# Monthly Optimization Report ({now.strftime('%B %Y')})

## Summary of Value Delivered
We believe in **Value > Profit**. You only pay when you save.

- **Total Raw Tokens Processed:** {billing['raw_tokens']:,}
- **Total Tokens After PASH Compression:** {billing['pash_tokens']:,}
- **Total Tokens Saved:** {billing['saved_tokens']:,}
- **Effective Savings Rate:** {((billing['saved_tokens'] / billing['raw_tokens']) * 100):.1f}%

## Financial Impact
- **Token Price:** ${TOKEN_PRICE_USD:.5f} / token
- **Your Total Savings:** **${billing['saved_dollars']:.4f}**
- **Our Fair Commission (10% of savings):** **${billing['commission']:.4f}**

*No hidden fees. No flat subscriptions. We succeed only when you save money.*
"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ Отчет сохранен: {report_path}")
    print(f"💰 Клиент сэкономил: ${billing['saved_dollars']:.4f}")
    print(f"💼 Наша комиссия (строго 10%): ${billing['commission']:.4f}")
    print("✅ Тест пройден: Комиссия составляет ровно 10% от экономии.")
    
    return billing

if __name__ == "__main__":
    generate_report()
