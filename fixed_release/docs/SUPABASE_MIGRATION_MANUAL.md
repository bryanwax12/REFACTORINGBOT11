# 📋 РУЧНАЯ МИГРАЦИЯ В SUPABASE

Из-за ограничений сети в Emergent, миграцию нужно выполнить вручную.

## ШАГ 1: Создание схемы в Supabase

1. Откройте ваш Supabase проект: https://yebbxwwlgexmpzbxinwg.supabase.co
2. В левом меню нажмите **SQL Editor**
3. Нажмите **"New query"**
4. Скопируйте **ВЕСЬ** код из файла `/app/supabase_schema.sql`
5. Вставьте в SQL Editor
6. Нажмите **"Run"** (или Ctrl+Enter)
7. Должно появиться "Success" ✅

---

## ШАГ 2: Экспорт данных из MongoDB (готово)

Данные уже экспортированы в `/app/mongodb_backup/`:
- `users.json` - 5 пользователей
- `orders.json` - 3 заказа
- `payments.json` - 18 платежей
- `settings.json` - 2 настройки

---

## ШАГ 3: Импорт данных в Supabase

### Вариант A: Через SQL Editor (быстро)

Откройте SQL Editor в Supabase и выполните по очереди:

#### 3.1 Импорт users:
```sql
-- Замените данные ниже на реальные из mongodb_backup/users.json
INSERT INTO users (telegram_id, username, first_name, last_name, balance, blocked, is_channel_member)
VALUES 
  (7066790254, 'White_Label_Shipping_Bot_Agent', '''White Label Shipping Bot'' Agent', '', 157.41, false, true),
  (123456789, 'test_user', 'Test', 'User', 0, false, false),
  (1579798535, 'Unknown_Art1st', 'Unknown', '', 0, false, false),
  (1787422426, 'Beardy8', 'Beardy', '', 0, false, false),
  (7175967023, 'bober20051', 'Bober', '', 0, false, false)
ON CONFLICT (telegram_id) DO NOTHING;
```

#### 3.2 Импорт settings:
```sql
INSERT INTO settings (key, value)
VALUES 
  ('api_mode', 'test'),
  ('last_updated', '2024-11-20')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
```

#### 3.3 Импорт orders и payments:
(Если есть данные - добавьте аналогично)

### Вариант B: Через Python скрипт локально

Если у вас есть Python на локальном компьютере:

1. Установите: `pip install asyncpg motor`
2. Скачайте `/app/migrate_to_supabase.py` на свой компьютер
3. Запустите:
```bash
SUPABASE_URL='postgresql://postgres:parol1234rqwrq@db.yebbxwwlgexmpzbxinwg.supabase.co:5432/postgres' python migrate_to_supabase.py
```

---

## ШАГ 4: Проверка данных

В SQL Editor выполните:
```sql
SELECT COUNT(*) as user_count FROM users;
SELECT COUNT(*) as order_count FROM orders;
SELECT COUNT(*) as payment_count FROM payments;
SELECT COUNT(*) as setting_count FROM settings;
```

Должно вернуть:
- users: 5
- orders: 3 (если были)
- payments: 18 (если были)
- settings: 2

---

## ШАГ 5: Обновление кода

Я обновлю код для работы с PostgreSQL вместо MongoDB.

**Дайте знать когда выполните Шаги 1-4, и я продолжу!**

---

## 📝 БЫСТРЫЙ СПОСОБ - Импорт 5 пользователей:

Просто выполните этот SQL в Supabase SQL Editor:

```sql
INSERT INTO users (telegram_id, username, first_name, last_name, balance, blocked, is_channel_member)
VALUES 
  (7066790254, 'White_Label_Shipping_Bot_Agent', '''White Label Shipping Bot'' Agent', '', 157.41, false, true),
  (123456789, 'test_user', 'Test', 'User', 0, false, false),
  (1579798535, 'Unknown_Art1st', 'Unknown', '', 0, false, false),
  (1787422426, 'Beardy8', 'Beardy', '', 0, false, false),
  (7175967023, 'bober20051', 'Bober', '', 0, false, false)
ON CONFLICT (telegram_id) DO NOTHING;

INSERT INTO settings (key, value)
VALUES 
  ('api_mode', 'test')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Проверка
SELECT * FROM users;
SELECT * FROM settings;
```

**Это минимум для запуска! Остальные данные (orders, payments) можно добавить потом.**
