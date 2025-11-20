-- Supabase PostgreSQL Schema for Telegram Shipping Bot
-- Migration from MongoDB Atlas to Supabase

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (from MongoDB users collection)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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

-- Orders table (from MongoDB orders collection)
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(255) UNIQUE NOT NULL,
    telegram_id BIGINT NOT NULL,
    from_name VARCHAR(255),
    from_company VARCHAR(255),
    from_street1 TEXT,
    from_street2 TEXT,
    from_city VARCHAR(255),
    from_state VARCHAR(50),
    from_zip VARCHAR(20),
    from_country VARCHAR(10) DEFAULT 'US',
    from_phone VARCHAR(50),
    to_name VARCHAR(255),
    to_company VARCHAR(255),
    to_street1 TEXT,
    to_street2 TEXT,
    to_city VARCHAR(255),
    to_state VARCHAR(50),
    to_zip VARCHAR(20),
    to_country VARCHAR(10) DEFAULT 'US',
    to_phone VARCHAR(50),
    weight DECIMAL(10, 2),
    length DECIMAL(10, 2),
    width DECIMAL(10, 2),
    height DECIMAL(10, 2),
    service_code VARCHAR(50),
    label_url TEXT,
    tracking_number VARCHAR(255),
    shipment_cost DECIMAL(10, 2),
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

-- Payments table (from MongoDB payments collection)
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id VARCHAR(255) UNIQUE NOT NULL,
    telegram_id BIGINT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'pending',
    payment_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

-- Settings table (from MongoDB settings collection)
CREATE TABLE settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Templates table (user shipping templates)
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT NOT NULL,
    template_name VARCHAR(255) NOT NULL,
    from_name VARCHAR(255),
    from_company VARCHAR(255),
    from_street1 TEXT,
    from_street2 TEXT,
    from_city VARCHAR(255),
    from_state VARCHAR(50),
    from_zip VARCHAR(20),
    from_country VARCHAR(10) DEFAULT 'US',
    from_phone VARCHAR(50),
    to_name VARCHAR(255),
    to_company VARCHAR(255),
    to_street1 TEXT,
    to_street2 TEXT,
    to_city VARCHAR(255),
    to_state VARCHAR(50),
    to_zip VARCHAR(20),
    to_country VARCHAR(10) DEFAULT 'US',
    to_phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

-- User sessions table (for conversation state)
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    session_data JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

-- Refund requests table
CREATE TABLE refund_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT NOT NULL,
    order_id VARCHAR(255),
    label_url TEXT,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

-- Indexes for performance (CRITICAL for speed!)
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_orders_telegram_id ON orders(telegram_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_payments_telegram_id ON payments(telegram_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_templates_telegram_id ON templates(telegram_id);
CREATE INDEX idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_sessions_active ON user_sessions(is_active) WHERE is_active = true;

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_settings_updated_at BEFORE UPDATE ON settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_templates_updated_at BEFORE UPDATE ON templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON user_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE users IS 'Telegram bot users';
COMMENT ON TABLE orders IS 'Shipping orders created by users';
COMMENT ON TABLE payments IS 'Payment transactions';
COMMENT ON TABLE settings IS 'Application settings (key-value pairs)';
COMMENT ON TABLE templates IS 'User-saved shipping address templates';
COMMENT ON TABLE user_sessions IS 'Active user conversation sessions';
COMMENT ON TABLE refund_requests IS 'User refund requests for labels';
