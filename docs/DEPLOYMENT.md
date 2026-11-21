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


## Render Free Blueprint

The root [render.yaml](../render.yaml) selects a Free Docker web service with a health probe at `/api/health` and automatic deploys disabled. The Docker command starts one Uvicorn process on `0.0.0.0` and the platform-provided `PORT`, or 8000 for local Docker. It retains the existing geospatial dependencies and limits numerical library threading to one thread through environment settings in the Blueprint. [Render Web Services](https://render.com/docs/web-services) ? [Blueprint reference](https://render.com/docs/blueprint-spec) ? [Free resources](https://render.com/docs/compute-plans)

With `DEMO_PUBLIC_READONLY=true`, each Docker launch selects a fresh temporary SQLite database and seeds it from the bundled synthetic fixture before opening the port. The API rejects methods other than GET, HEAD and OPTIONS before parsing request bodies. The import form and restore control are hidden, and the upload operation is excluded from the public OpenAPI schema. Downloads, maps, filtering and analyses remain available. The Windows launcher and local Docker default continue to support imports. Render Free filesystem changes are ephemeral and the service can spin down while idle. [Render Free behavior](https://render.com/docs/free)

After explicit authorization to create and push the GitHub repository and deploy the service:

1. Push the reviewed branch and confirm the GitHub Verify run. The workflow includes a public-mode container test on port 10000 under a 0.1 CPU and 512 MiB Docker limit.
2. Import the root Blueprint from the reviewed repository in the authorized Render workspace. Confirm the Free Docker plan, no disk or external database, and `DEMO_PUBLIC_READONLY=true`. Apply only after approval to deploy.
3. Confirm the startup log shows the seed succeeded, the service is listening on the selected port, and the health check is green. Add the actual HTTPS URL to the README.
4. Run the smoke script against that HTTPS URL with `--public`. In a real browser, verify HTTPS, the home page, map layers, filtering, analytics, downloads, mobile layout, and write restrictions. Record the actual Render logs and GitHub Actions run in the release report.
