#!/usr/bin/env python3
"""
Test markup application to rates
"""

# Симуляция того, как применяется markup
rates = [
    {'carrier': 'UPS', 'service': 'Ground', 'amount': 17.43},
    {'carrier': 'USPS', 'service': 'Priority', 'amount': 8.19},
    {'carrier': 'FedEx', 'service': 'Express', 'amount': 25.50}
]

LABEL_MARKUP = 10.0

print("🧪 Тест применения надбавки $10 к тарифам")
print("=" * 60)
print()

for rate in rates:
    original_amount = rate['amount']
    rate['original_amount'] = original_amount
    rate['amount'] = original_amount + LABEL_MARKUP
    
    print(f"📦 {rate['carrier']} - {rate['service']}")
    print(f"   Оригинальная цена: ${original_amount:.2f}")
    print(f"   Цена с надбавкой:  ${rate['amount']:.2f}")
    print(f"   Надбавка:          ${LABEL_MARKUP:.2f}")
    print()

print("=" * 60)
print("✅ Надбавка применяется ко всем тарифам!")
print()
print("Пример:")
print(f"  Если ShipStation вернул цену $8.19")
print(f"  Пользователь увидит и заплатит: $18.19")
print(f"  Ваша прибыль с лейбла: $10.00")
