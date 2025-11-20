-- ЧАСТЬ 1: Создание таблиц (выполните это первым)
-- Скопируйте и выполните в Supabase SQL Editor

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    balance DECIMAL(10, 2) DEFAULT 0.00,
    blocked BOOLEAN DEFAULT false,
    is_channel_member BOOLEAN DEFAULT false,
    channel_status_checked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);

-- ЧАСТЬ 2: Вставка данных (выполните после Части 1)
INSERT INTO users (telegram_id, username, first_name, last_name, balance, blocked, is_channel_member)
VALUES 
  (7066790254, 'White_Label_Shipping_Bot_Agent', 'White Label Shipping Bot Agent', '', 157.41, false, true),
  (123456789, 'test_user', 'Test', 'User', 0, false, false),
  (1579798535, 'Unknown_Art1st', 'Unknown', '', 0, false, false),
  (1787422426, 'Beardy8', 'Beardy', '', 0, false, false),
  (7175967023, 'bober20051', 'Bober', '', 0, false, false)
ON CONFLICT (telegram_id) DO NOTHING;

INSERT INTO settings (key, value)
VALUES ('api_mode', 'test')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Проверка
SELECT 'Users count:', COUNT(*) FROM users;
SELECT 'Settings count:', COUNT(*) FROM settings;
