# Local and optional container deployment

Use the Windows launcher in the project root to create the environment and seed the SQLite demo. The default installation requires no container runtime. Use an IANA zone such as `America/Los_Angeles` in `STUDY_TIMEZONE` if you want local study dates. Environment values are read from the process; `.env.example` is a reference.

## Opt-in restore on a dedicated SQLite database

Run the following in PowerShell from the project root. Choose a fresh database filename. The seeder refuses to mark a database containing observations, participants or import history.

```powershell
$env:DATABASE_URL = "sqlite:///./resettable-demo.db"
$env:DEMO_RESET_ENABLED = "1"
.\.venv\Scripts\python.exe -m app.demo_seed --mark-demo
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The dashboard displays **Restore demo data** only for an eligible local database. After confirmation it replaces imported demo data and history with the canonical 366 rows in one transaction. Keep this option disabled for any service exposed through a proxy.

## Docker template

```powershell
docker build --tag wearable-mobility-research-pipeline:1.0.0 .
docker run --rm -p 127.0.0.1:8000:8000 -v mobility-demo:/var/lib/mobility wearable-mobility-research-pipeline:1.0.0
```

The image runs as a non-root service user and probes `/api/health`. Its volume contains SQLite state. This is a synthetic demo template awaiting Docker runtime verification. A low-cost host would need an appropriately attached persistent volume, approved exposure, and HTTPS. No cloud deployment is included.


## MySQL and local tooling

Create a dedicated synthetic-only database with a case-sensitive UTF-8 collation and a database-scoped account. Configure `DATABASE_URL` with the `mysql+pymysql` scheme and an approved TLS configuration. Use `python -m app.demo_seed` to apply migrations and seed it. The optional `mysql` Compose profile binds only to local port 3307 and requires passwords in the process environment. The actual server acceptance used a local temporary MySQL 9.0 instance.

```powershell
docker compose --profile mysql up -d mysql
```

The following commands use the currently selected synthetic database:

```powershell
.\.venv\Scripts\python.exe -m app.wearable_adapter
.\.venv\Scripts\python.exe -m app.analysis_run SYN-P001 --date 2026-11-16
.\.venv\Scripts\python.exe -m app.analysis_run SYN-P001 --list
```

The wearable fixture is locally simulated with Fitbit-shaped fields and uses no account, OAuth or external API. Run history records daily metrics and their input fingerprint.

## Low-cost public portfolio configuration

Use one small Linux container instance with ingress on port 8000, TLS handled by the host, and a health probe at `/api/health`. Set `DEMO_READ_ONLY=1` and `DEMO_RESET_ENABLED=0` for public viewing. A disposable SQLite database can be seeded on each fresh instance for the read-only demo. Mount a volume at `/var/lib/mobility` only if persistence is needed. Use the default Linux database path in the image and omit MySQL for this deployment. This design needs no secrets, Windows paths, paid API, or provider-specific integration. Select a service and verify its actual price before deploying.

After starting the image, run the following from the source checkout:

```text
python -m scripts.smoke_release http://127.0.0.1:8000
```
