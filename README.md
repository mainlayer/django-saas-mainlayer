# Django SaaS Starter — Powered by Mainlayer

A production-ready Django SaaS starter that uses [Mainlayer](https://mainlayer.fr) for payment infrastructure. Clone it, add your API key, and have a billing-enabled SaaS running in minutes.

## What's included

- **Custom User model** with subscription tier tracking
- **Mainlayer billing client** (`billing/mainlayer.py`) — thin `httpx` wrapper around the Mainlayer REST API
- **Three-tier pricing page** — Free, Pro ($29/mo), Enterprise ($99/mo)
- **Subscribe flow** — calls `POST /pay`, redirects to Mainlayer-hosted checkout
- **Entitlement checks** — verifies active access via `GET /entitlements/check`
- **Customer portal** — redirects to `POST /portal` for subscription management
- **Dashboard** with plan status, feature list, and upgrade prompt
- **Auth** — register, login, logout, settings
- **Tailwind CSS** (CDN) — clean, responsive UI out of the box
- **Docker + docker-compose** — one-command deployment
- **Test suite** — unit tests for the client, views, and models

## Project structure

```
django-saas-mainlayer/
├── saas/                  # Django project package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── accounts/          # Custom User model, auth views
│   ├── billing/           # Mainlayer client, Subscription model, views
│   └── dashboard/         # Post-login home page
├── templates/             # HTML templates (base + per-app)
├── static/css/main.css    # Supplemental styles
├── tests/                 # pytest test suite
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Quick start

### 1. Clone and install

```bash
git clone <repo-url>
cd django-saas-mainlayer

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Long random Django secret key |
| `MAINLAYER_API_KEY` | Your Mainlayer API key |
| `MAINLAYER_RESOURCE_ID_PRO` | Resource ID for the Pro plan |
| `MAINLAYER_RESOURCE_ID_ENTERPRISE` | Resource ID for the Enterprise plan |

Get your API key and create resource IDs at [mainlayer.fr](https://mainlayer.fr).

### 3. Run migrations and start

```bash
python manage.py migrate
python manage.py createsuperuser   # optional
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000) — you'll be redirected to the dashboard.

## Docker deployment

```bash
cp .env.example .env
# Edit .env with your real keys

docker compose up --build
```

The app will be available at [http://localhost:8000](http://localhost:8000).

## Mainlayer billing flow

```
User clicks "Subscribe"
       |
  POST /pay  (billing/views.py -> billing/mainlayer.py)
       |
  Mainlayer returns payment_url
       |
  User completes payment on Mainlayer-hosted page
       |
  Mainlayer redirects to /billing/success/?tier=pro
       |
  GET /entitlements/check  (verify payment landed)
       |
  Subscription model updated -> user gains access
```

## Running tests

```bash
pytest
```

The test suite mocks all Mainlayer HTTP calls using `httpx`'s mock transport — no API key needed.

## Customising plans

Plans are defined in `saas/settings.py` under `MAINLAYER_PLANS`. Each key maps to a resource ID, price, and feature list:

```python
MAINLAYER_PLANS = {
    "pro": {
        "name": "Pro",
        "resource_id": env("MAINLAYER_RESOURCE_ID_PRO"),
        "price": 29,
        "features": ["Unlimited projects", "50 GB storage", ...],
    },
}
```

Add or remove tiers here — the pricing page and subscribe flow pick them up automatically.

## Production checklist

- [ ] Set `DEBUG=False` and a strong `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Use a PostgreSQL `DATABASE_URL`
- [ ] Run `python manage.py collectstatic`
- [ ] Serve via gunicorn behind nginx or a platform like Railway / Render / Fly.io
- [ ] Set up Mainlayer webhook (optional) to handle async payment events

## License

MIT
