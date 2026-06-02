-- Supabase PostgreSQL Schema for API Monitoring SaaS

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'company',
    company_id TEXT,
    employee_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Employee Invitations table
CREATE TABLE IF NOT EXISTS employee_invitations (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    company_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (company_id) REFERENCES users(id) ON DELETE CASCADE
);

-- API Endpoints table
CREATE TABLE IF NOT EXISTS api_endpoints (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL,
    created_by TEXT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    method TEXT DEFAULT 'GET',
    interval INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    api_key TEXT,
    api_key_header TEXT DEFAULT 'Authorization',
    auth_type TEXT DEFAULT 'header',
    key_status TEXT,
    last_validated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Monitoring Logs table
CREATE TABLE IF NOT EXISTS monitoring_logs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    endpoint_id TEXT NOT NULL,
    status_code INTEGER DEFAULT 0,
    response_time REAL,
    is_success BOOLEAN DEFAULT FALSE,
    api_key_status TEXT,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE
);

-- Email Verifications (OTP) table
CREATE TABLE IF NOT EXISTS email_verifications (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email TEXT NOT NULL,
    otp TEXT NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id);
CREATE INDEX IF NOT EXISTS idx_invitations_token ON employee_invitations(token);
CREATE INDEX IF NOT EXISTS idx_endpoints_user_id ON api_endpoints(user_id);
CREATE INDEX IF NOT EXISTS idx_endpoints_created_by ON api_endpoints(created_by);
CREATE INDEX IF NOT EXISTS idx_logs_endpoint_id ON monitoring_logs(endpoint_id);
CREATE INDEX IF NOT EXISTS idx_logs_checked_at ON monitoring_logs(checked_at);
CREATE INDEX IF NOT EXISTS idx_email_verif_email ON email_verifications(email);
