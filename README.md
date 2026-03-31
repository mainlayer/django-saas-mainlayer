# Django SaaS Starter — Mainlayer Billing

A production-ready Django SaaS with **Mainlayer** payment infrastructure. Full authentication, 3-tier pricing, subscription management, dashboard with usage tracking, and webhooks. Docker-ready.

Perfect for:
- Building SaaS products in Django
- Selling subscriptions (Free / Pro / Enterprise)
- Integrating Mainlayer for payment processing
- Running on Railway, Render, Fly.io, or any WSGI host

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

## Quickstart (5 minutes)

### 1. Clone & install

```bash
git clone https://github.com/yourorg/django-saas-mainlayer.git
cd django-saas-mainlayer

# With Docker (recommended)
docker compose up

# Or: virtualenv + pip
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Django
SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=false

# Database (auto-configured in docker-compose)
DATABASE_URL=postgresql://saas:saas@localhost:5432/saas

# Mainlayer
MAINLAYER_API_KEY=ml_live_xxxxxxxxxxxxxxxxxxxx
MAINLAYER_RESOURCE_ID_PRO=res_pro_xxxx
MAINLAYER_RESOURCE_ID_ENTERPRISE=res_ent_xxxx

# Email (for transactional emails)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<your SendGrid key>
```

### 3. Migrate and run

```bash
# With Docker
docker compose up
# Then open http://localhost:8000

# Without Docker
python manage.py migrate
python manage.py createsuperuser  # Create admin user (optional)
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000) → you're directed to the dashboard if authenticated.

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

## Syncing subscriptions with Mainlayer

Use the `sync_subscriptions` management command to periodically verify and sync subscriptions:

```bash
# Check entitlements for all active subscriptions
python manage.py sync_subscriptions

# Also update user model fields (subscription_tier, subscription_active)
python manage.py sync_subscriptions --update-user-fields

# Verbose output
python manage.py sync_subscriptions --verbosity 2
```

This command:
1. Queries all Subscription records with paid plans (pro, enterprise)
2. Calls `GET /entitlements/check` on Mainlayer for each
3. Updates local `is_active` status based on Mainlayer response
4. Optionally syncs user model shortcut fields
5. Logs any changes or failures

**Recommended**: Run this daily via cron or Celery:

```bash
# In your crontab
0 1 * * * cd /opt/saas && python manage.py sync_subscriptions --update-user-fields
```

Or with Celery:

```python
# In celerybeat config
CELERY_BEAT_SCHEDULE = {
    'sync-subscriptions': {
        'task': 'billing.tasks.sync_subscriptions',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}
```

---

## Running tests

```bash
pytest

# With coverage
pytest --cov=billing --cov=dashboard --cov=accounts

# Only billing tests
pytest tests/ -k billing -v
```

The test suite mocks all Mainlayer HTTP calls — no API key needed.

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

## Billing flow

```
User registers → Dashboard (Free plan)
       ↓
User clicks "Upgrade to Pro" → Pricing page
       ↓
POST /billing/subscribe/pro → Create Mainlayer payment
       ↓
Redirect to Mainlayer checkout → User pays
       ↓
POST /billing/success/?tier=pro → Verify entitlement
       ↓
GET /entitlements/check ← Mainlayer confirms
       ↓
subscription.mark_active(tier='pro', ...) → Update DB
       ↓
User now has access to Pro features
```

---

## Customizing plans

Edit `saas/settings.py` under `MAINLAYER_PLANS`:

```python
MAINLAYER_PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "resource_id": None,
        "features": [
            "Up to 3 projects",
            "Basic support",
            "Community access",
        ],
    },
    "pro": {
        "name": "Pro",
        "price": 29,
        "resource_id": env("MAINLAYER_RESOURCE_ID_PRO"),
        "features": [
            "Unlimited projects",
            "Priority email support",
            "Advanced analytics",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 99,
        "resource_id": env("MAINLAYER_RESOURCE_ID_ENTERPRISE"),
        "features": [
            "Everything in Pro",
            "Dedicated support",
            "SSO / SAML",
            "SLA guarantee",
        ],
    },
}
```

Create the resources in [Mainlayer dashboard](https://mainlayer.fr/dashboard), then update `.env`:

```env
MAINLAYER_RESOURCE_ID_PRO=res_pro_xxx
MAINLAYER_RESOURCE_ID_ENTERPRISE=res_ent_xxx
```

---

## Deploying to production

### Docker (Railway, Render, Fly.io)

```bash
# Build image
docker build -t my-saas .

# Push to registry and deploy
# The Dockerfile uses gunicorn + Django for production
```

### Environment variables

```env
# Security
DEBUG=false
SECRET_KEY=<strong random value>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:pass@prod-db:5432/saas

# Mainlayer
MAINLAYER_API_KEY=ml_live_xxx
MAINLAYER_RESOURCE_ID_PRO=res_pro_xxx
MAINLAYER_RESOURCE_ID_ENTERPRISE=res_ent_xxx

# Email
EMAIL_HOST=smtp.sendgrid.net
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<SendGrid API key>
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Security (HTTPS)
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

### Deployment checklist

- [ ] Set `DEBUG=False`
- [ ] Use a strong `SECRET_KEY` (generate with Django command above)
- [ ] Configure `ALLOWED_HOSTS` for your domain(s)
- [ ] Use PostgreSQL (not SQLite) with backups
- [ ] Enable HTTPS and set `SECURE_SSL_REDIRECT=True`
- [ ] Run `python manage.py collectstatic` before deploying
- [ ] Set up error tracking (Sentry, Rollbar)
- [ ] Configure email backend (SendGrid, Mailgun, etc.)
- [ ] Schedule `sync_subscriptions` command (daily)
- [ ] Test payment flow end-to-end
- [ ] Set up monitoring & uptime alerts

---

## Troubleshooting

**"AttributeError: 'AnonymousUser' has no attribute 'subscription'"**
- You're accessing subscription on an unauthenticated user
- Check that your view/template has `@login_required` or authentication check

**"Mainlayer API error: Invalid resource_id"**
- Verify resource IDs match what's in Mainlayer dashboard
- Check env vars are set correctly
- Ensure you're using correct environment (dev vs. prod keys)

**"Subscription not updating after payment"**
- Check webhook logs in Django admin
- Verify Mainlayer webhook is registered and firing
- Try running `python manage.py sync_subscriptions` to manually sync
- Check Mainlayer dashboard for the payment

**"500 error on /billing/subscribe"**
- Check `MAINLAYER_API_KEY` is set and valid
- Verify plan's resource_id is configured
- Check Mainlayer API status at https://status.mainlayer.fr
- Review Django logs for full error

**"entitlement_checked_at is in the future"**
- This shouldn't happen; contact support with the subscription ID

---

## Support & docs

- **Mainlayer docs**: https://docs.mainlayer.fr
- **Mainlayer API**: https://api.mainlayer.fr
- **Django docs**: https://docs.djangoproject.com
- **Email setup**: https://docs.djangoproject.com/en/stable/topics/email/

## License

MIT
