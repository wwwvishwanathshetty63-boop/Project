# 📡 API Monitor SaaS

Production-ready SaaS-based API Monitoring & Alert System built with Flask, Supabase, and vanilla HTML/CSS/JS.

## Features

- **Real-time API Monitoring** — Automatic health checks every 60 seconds
- **Instant Email Alerts** — Notifications on failures, timeouts, and consecutive errors
- **Analytics Dashboard** — Uptime %, response times, error rates with Chart.js graphs
- **JWT Authentication** — Secure registration, login, and role-based access control
- **Endpoint Management** — Add, edit, delete, and toggle monitoring per endpoint
- **Row Level Security** — Users can only access their own data

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask |
| Database | Supabase (PostgreSQL) |
| Frontend | HTML, CSS, JavaScript |
| Charts | Chart.js |
| Auth | JWT + bcrypt |
| Alerts | SMTP (smtplib) |
| Scheduler | APScheduler |

## Quick Start

### 1. Clone and install dependencies

```bash
cd api-monitoring-saas
pip install -r requirements.txt
```

### 2. Set up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the following migration:

```sql
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- API Endpoints table
CREATE TABLE IF NOT EXISTS api_endpoints (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    url TEXT NOT NULL,
    method VARCHAR(10) DEFAULT 'GET',
    interval INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_endpoints_user_id ON api_endpoints(user_id);

-- Monitoring Logs table
CREATE TABLE IF NOT EXISTS monitoring_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    endpoint_id UUID NOT NULL REFERENCES api_endpoints(id) ON DELETE CASCADE,
    status_code INTEGER DEFAULT 0,
    response_time FLOAT,
    is_success BOOLEAN DEFAULT false,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_logs_endpoint_id ON monitoring_logs(endpoint_id);
CREATE INDEX idx_logs_checked_at ON monitoring_logs(checked_at);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_endpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policies (allow all for service role / anon key with app-level auth)
CREATE POLICY "Allow all operations on users" ON users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on api_endpoints" ON api_endpoints FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on monitoring_logs" ON monitoring_logs FOR ALL USING (true) WITH CHECK (true);
```

3. Copy your **Project URL** and **anon key** from Settings → API

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your Supabase URL, key, JWT secret, and SMTP credentials
```

### 4. Run the application

```bash
python run.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Project Structure

```
api-monitoring-saas/
├── backend/
│   ├── app.py                  # Flask app factory
│   ├── config.py               # Environment configuration
│   ├── monitoring_engine.py    # APScheduler background jobs
│   ├── models/
│   │   └── __init__.py         # Supabase client
│   ├── routes/
│   │   ├── auth_routes.py      # Register, login, profile
│   │   ├── endpoint_routes.py  # CRUD for API endpoints
│   │   └── dashboard_routes.py # Stats and chart data
│   ├── services/
│   │   ├── alert_service.py    # SMTP email alerts
│   │   └── monitoring_service.py # Health check logic
│   └── utils/
│       ├── auth.py             # JWT helpers & decorators
│       └── validators.py       # Input validation
├── frontend/
│   ├── index.html              # Landing page (login/register)
│   ├── dashboard.html          # Dashboard with stats & charts
│   ├── css/
│   │   └── styles.css          # Design system
│   └── js/
│       ├── app.js              # Auth & API client
│       └── dashboard.js        # Dashboard logic
├── run.py                      # Application entry point
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

### Authentication
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and get JWT |
| GET | `/api/auth/profile` | Get user profile |
| PUT | `/api/auth/profile` | Update profile |

### Endpoints Management
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/endpoints` | Add new endpoint |
| GET | `/api/endpoints` | List all endpoints |
| GET | `/api/endpoints/:id` | Get single endpoint |
| PUT | `/api/endpoints/:id` | Update endpoint |
| DELETE | `/api/endpoints/:id` | Delete endpoint |
| PATCH | `/api/endpoints/:id/toggle` | Toggle monitoring |
| GET | `/api/endpoints/:id/logs` | Get monitoring logs |

### Dashboard
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/dashboard/stats` | Dashboard statistics |
| GET | `/api/dashboard/response-times` | Chart data (24h) |

## Email Alerts

Alerts are sent via SMTP when:
- HTTP status code is not 2xx
- Request times out
- 3 consecutive failures are detected (CRITICAL alert)

Configure SMTP in `.env`. For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833).

## Deployment

### Production settings
```bash
FLASK_DEBUG=false
PORT=8080
SECRET_KEY=<long-random-string>
JWT_SECRET=<different-long-random-string>
```

### Docker (optional)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "run.py"]
```

## Security

- JWT authentication on all API routes
- bcrypt password hashing
- Input validation on all endpoints
- CORS configuration
- Rate limiting (200 requests/hour default)
- No hardcoded secrets — all via environment variables
- Row Level Security enabled on all Supabase tables

## License

MIT
