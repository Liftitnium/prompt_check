# PromptCheck

Regression testing for LLM prompts. A team saves each version of a prompt together with a set of test cases, runs every version through an LLM, and sees exactly which test cases regressed before shipping a prompt change.

**Stakeholder:** an 8-person AI team at a Spanish e-commerce startup whose support assistant runs on ~20 prompts that change weekly. Changes break behaviour silently (wrong language, invalid JSON, missing refund policy); PromptCheck catches that before customers do.

**Live:** https://rnasrallahieu2024ui.z1.web.core.windows.net

The services scale to zero when idle, so the first request after a quiet period can take up to a minute while the container starts and the database resumes. The UI shows "Waking up the … service" and retries.

## Architecture

Two services, each with its own database, plus a static UI:

- **prompts** (`services/prompts`): prompts, their immutable numbered versions, and test cases. Owns the prompts database.
- **evals** (`services/evals`): eval runs, per-test-case results, and run comparisons. Owns the evals database. When a run is created it calls prompts' `GET /versions/{version_id}/for-run` (2 s timeout) and snapshots the template and test cases. If prompts is down, creating a run returns 503 with a clear message; stored runs keep working.
- **ui** (`ui/`): static HTML/CSS/JS that calls both services. The service URLs come from `ui/config.js`, which the deploy overwrites.

[`system.yaml`](system.yaml) describes every service, its environment variables, its call across the seam and its Azure resources (validated in CI against [`system.schema.json`](system.schema.json)). Each service's API is in `services/<name>/openapi.yaml`. Design decisions are in [ADR.md](ADR.md).

## Run the whole system locally (Docker Compose)

```bash
cp .env.example .env      # then fill in the three passwords (and LLM_* if you want the real API)
docker compose up --build
```

- UI: http://localhost:8080
- prompts: http://localhost:8001 (`/docs`, `/health`)
- evals: http://localhost:8002 (`/docs`, `/health`)

Compose starts SQL Server, a one-off `db-init` container that creates the two databases and each service's login ([`db/init.sql`](db/init.sql), safe to re-run), then both services. Each service applies its own migrations on startup, and prompts loads the demo data into an empty database. Data lives on the `sqlserver-data` volume and survives `docker compose down` (not `down -v`).

The SQL Server image has no arm64 build; on Apple Silicon it runs under Docker's Rosetta emulation. SQL Server 2022 crashed there, so compose uses 2025 (ADR-7).

To see partial failure: `docker compose stop prompts`. Evals still lists runs and results; creating a run shows "the prompts service is unavailable; try again later". `docker compose start prompts` brings it back.

## Run a single service

With compose, start just one service and what it needs (SQL Server and `db-init`):

```bash
docker compose up --build prompts      # or: evals (runs work only if prompts is up too)
```

Or run it directly from its folder against the compose database, with Python 3.14:

```bash
docker compose up -d sqlserver db-init
cd services/prompts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
set -a; source ../../.env; set +a
DATABASE_URL="mssql://prompts_app:${PROMPTS_DB_PASSWORD}@localhost:1433/promptcheck_prompts" PORT=8001 python -m app
```

For evals use `services/evals`, `evals_app`, `${EVALS_DB_PASSWORD}`, `promptcheck_evals`, `PORT=8002`, and `PROMPTS_URL=http://localhost:8001`. Every variable a service reads is listed with its default in [`system.yaml`](system.yaml).

## Tests and coverage

Unit and service tests run per service against a real SQL Server (the compose one is fine); every test starts from an empty schema built by the real migrations, and the LLM is faked.

```bash
docker compose up -d sqlserver
set -a; source .env; set +a
cd services/evals            # or services/prompts
pip install -r requirements-dev.txt
TEST_DATABASE_URL="mssql://sa:${SA_PASSWORD}@localhost:1433/promptcheck_test_evals" \
  python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70
ruff check .
```

Current result: prompts 94%, evals 97% coverage.

The cross-seam integration test runs against the whole compose stack over HTTP, including stopping prompts to check the designed failure:

```bash
docker compose up -d --build
pip install -r tests/integration/requirements.txt
python -m pytest tests/integration -v
```

## How deployment works

Every change reaches `main` through a pull request.

- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every branch push and pull request. Per service: ruff, OpenAPI validation, tests with a 70% coverage gate against a SQL Server service container. Then `system.yaml` is checked against `system.schema.json`, the cross-seam integration test runs against the compose stack, and both images are built.
- **CD** ([`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)) runs on every push to `main`. It first calls `ci.yml`, so nothing deploys unless CI passed on the same commit, and the images are pushed to GHCR tagged with the commit SHA. The deploy job then:
  1. signs in to Azure as the managed identity `rnasrallah-ieu2024-github` through OpenID Connect (no stored Azure password);
  2. for each service, stores its database URL as a Container Apps secret and points the Container App at `ghcr.io/liftitnium/promptcheck-<service>:<sha>`, with min 0 / max 1 replicas, CORS limited to the UI's origin, and (for evals) prompts' HTTPS address as `PROMPTS_URL`;
  3. writes `ui/config.js` with both services' URLs and uploads `ui/` to the storage account's `$web` container;
  4. calls `/health` on both services until each returns 200 **with the deployed commit's SHA as its version**, failing the run after about 10 minutes.

Migrations run when the new container starts, never in the workflow.

### Azure resources

Everything is in the Azure for Students subscription, region `germanywestcentral`, resource group `rg-rnasrallah-ieu2024`:

- `rnasrallahieu2024ui`: storage account, static website (the UI)
- `rnasrallah-ieu2024-sql`: Azure SQL server, with `rnasrallah-ieu2024-prompts-db` and `rnasrallah-ieu2024-evals-db` (serverless, free offer, auto-pause after 60 min)
- `rnasrallah-ieu2024-env`: Container Apps environment (Consumption), sending logs to the `rnasrallah-ieu2024-logs` Log Analytics workspace
- `rnasrallah-ieu2024-prompts`, `rnasrallah-ieu2024-evals`: Container Apps
- `rnasrallah-ieu2024-github`: user-assigned managed identity used by the pipeline (Contributor on this resource group only)

### Reproducing the initial Azure setup

This was done once by hand with the Azure CLI; after it, only the pipeline changes anything. No password is written here: each one is typed into a hidden prompt or a shell variable and stored only as a GitHub secret.

Use a separate CLI profile if another Azure login (for example a group project in another directory) shares your machine:

```bash
export AZURE_CONFIG_DIR=$HOME/.azure-students
az login
az account set --subscription "<your Azure for Students subscription ID>"
PREFIX=rnasrallah-ieu2024; RG=rg-$PREFIX; LOC=germanywestcentral; UI_STORAGE=rnasrallahieu2024ui
```

`LOC` must be one of the five regions your subscription allows (`az policy assignment list`, "Allowed resource deployment regions").

**Step 2. Providers and resource group**

```bash
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace $ns --wait
done
az group create --name $RG --location $LOC
```

**Step 3. The UI: storage static website**

```bash
az storage account create --name $UI_STORAGE --resource-group $RG --location $LOC \
  --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false
az storage blob service-properties update --account-name $UI_STORAGE --static-website \
  --index-document index.html --auth-mode key
az storage account show --name $UI_STORAGE --resource-group $RG --query primaryEndpoints.web -o tsv
```

The last command prints the public URL. If the Homebrew `az` crashes on storage commands (a broken `pyexpat` in its Python), run that one command through the official image instead, passing the account key: `docker run --rm mcr.microsoft.com/azure-cli:latest az storage blob service-properties update ... --account-key "$KEY"`.

**Step 4. SQL server, two serverless databases, one user per database**

```bash
read -rs SQL_ADMIN_PW
az sql server create --name $PREFIX-sql --resource-group $RG --location $LOC \
  --admin-user pcadmin --admin-password "$SQL_ADMIN_PW"
az sql server firewall-rule create --resource-group $RG --server $PREFIX-sql \
  --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
for svc in prompts evals; do
  az sql db create --resource-group $RG --server $PREFIX-sql --name $PREFIX-$svc-db \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 --min-capacity 0.5 --capacity 1 \
    --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
done
```

Then open the firewall to your own IP, create each service's contained user in its own database, and close the firewall again. Run this once per service (`prompts`, `evals`), typing that service's password at the prompt:

```bash
az sql server firewall-rule create -g $RG -s $PREFIX-sql -n setup --start-ip-address <your IP> --end-ip-address <your IP>
svc=prompts; read -rs SVC_PW; export SQL_ADMIN_PW SVC_PW
docker run --rm --platform linux/amd64 -e SQL_ADMIN_PW -e SVC_PW --entrypoint bash \
  mcr.microsoft.com/mssql/server:2025-CU10-GDR1-ubuntu-22.04 -c \
  "/opt/mssql-tools18/bin/sqlcmd -S $PREFIX-sql.database.windows.net -d $PREFIX-$svc-db -U pcadmin -P \"\$SQL_ADMIN_PW\" -l 90 -b -Q \"
   CREATE USER ${svc}_app WITH PASSWORD = '\$SVC_PW';
   ALTER ROLE db_ddladmin ADD MEMBER ${svc}_app;
   ALTER ROLE db_datareader ADD MEMBER ${svc}_app;
   ALTER ROLE db_datawriter ADD MEMBER ${svc}_app;\""
az sql server firewall-rule delete -g $RG -s $PREFIX-sql -n setup
```

The databases pause after 60 minutes idle; the first connection after that fails with "not currently available" for about a minute while it resumes. Run it again.

**Step 5. Container Apps**

```bash
az monitor log-analytics workspace create -g $RG -n $PREFIX-logs -l $LOC
WS_ID=$(az monitor log-analytics workspace show -g $RG -n $PREFIX-logs --query customerId -o tsv)
WS_KEY=$(az monitor log-analytics workspace get-shared-keys -g $RG -n $PREFIX-logs --query primarySharedKey -o tsv)
az containerapp env create --name $PREFIX-env --resource-group $RG --location $LOC \
  --logs-destination log-analytics --logs-workspace-id "$WS_ID" --logs-workspace-key "$WS_KEY"
for svc in prompts evals; do
  az containerapp create --name $PREFIX-$svc --resource-group $RG --environment $PREFIX-env \
    --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi
done
```

The apps start on a placeholder image; the first deploy sets their image, the `database-url` secret and the environment variables. CORS is handled in the services (`ALLOWED_ORIGINS`), not by Container Apps ingress. The GHCR packages `promptcheck-prompts` and `promptcheck-evals` must be public so Azure can pull them.

**Step 6. The pipeline's identity (OIDC)**

```bash
az identity create --name $PREFIX-github --resource-group $RG --location $LOC
PRINCIPAL_ID=$(az identity show --name $PREFIX-github --resource-group $RG --query principalId -o tsv)
az role assignment create --assignee-object-id $PRINCIPAL_ID --assignee-principal-type ServicePrincipal \
  --role Contributor --scope $(az group show --name $RG --query id -o tsv)
az identity federated-credential create --name github-main --identity-name $PREFIX-github --resource-group $RG \
  --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange \
  --subject "repo:Liftitnium/prompt_check:ref:refs/heads/main"
```

GitHub may send the subject with numeric IDs instead of names (`repo:<owner>@<id>/<repo>@<id>:ref:refs/heads/main`), so a second credential, `github-main-ids`, registers that form too. If `azure/login` fails with "No matching federated identity record", the error shows the subject GitHub sent.

**Step 7. GitHub secrets and variables**

```bash
gh secret set AZURE_CLIENT_ID --body "$(az identity show --name $PREFIX-github --resource-group $RG --query clientId -o tsv)"
gh secret set AZURE_TENANT_ID --body "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID --body "$(az account show --query id -o tsv)"
gh secret set PROMPTS_DB_PASSWORD      # prompts for the value
gh secret set EVALS_DB_PASSWORD
gh variable set PREFIX --body $PREFIX
gh variable set RESOURCE_GROUP --body $RG
gh variable set UI_STORAGE --body $UI_STORAGE
```

**Step 8.** The CD workflow is [`deploy.yml`](.github/workflows/deploy.yml), described above.

**Step 9. Read access for grading**

```bash
for p in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  az role assignment create --assignee $p --role Reader --scope $(az group show --name $RG --query id -o tsv)
done
```

## API

prompts (port 8001 locally):

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{"status","db","version"}`: 200 if it can read and write its own database, else 503 |
| POST / GET | `/prompts` | Create a prompt / list prompts |
| GET | `/prompts/{id}` | Get one prompt |
| POST / GET | `/prompts/{id}/versions` | Publish the next version / list versions |
| GET | `/prompts/{id}/versions/{n}` | Get one version and its template variables |
| GET | `/prompts/{id}/versions/{a}/diff/{b}` | Line diff between two versions |
| POST / GET | `/prompts/{id}/test-cases` | Add a test case / list active test cases |
| DELETE | `/test-cases/{id}` | Archive a test case |
| GET | `/checks` | Available check types |
| GET | `/versions/{version_id}/for-run` | Template and active test cases for a run (called by evals) |

evals (port 8002 locally):

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Same contract as prompts; reflects only evals' own database |
| POST | `/runs` | Start a run for `{"prompt_version_id": n}`; 202, or 503 if prompts is unavailable |
| GET | `/runs?prompt_id=` | List runs, newest first |
| GET | `/runs/compare?base=&candidate=` | Regressions, fixes, pass-rate/latency/token deltas and a `ship`/`block` verdict |
| GET | `/runs/{id}` | Run status, pass rate and per-test-case results |
| POST | `/runs/{id}/rescore` | Re-score a completed run's stored outputs with the current checks, as a new run |

### Example: the seeded demo

The demo prompt `refund-reply` has two versions. v2 is an English rewrite that drops the refund policy, so two of its three test cases regress:

```bash
curl -X POST localhost:8002/runs -H 'content-type: application/json' -d '{"prompt_version_id": 1}'   # run 1
curl -X POST localhost:8002/runs -H 'content-type: application/json' -d '{"prompt_version_id": 2}'   # run 2
curl localhost:8002/runs/1               # poll until "status" is "completed" (pass_rate 1.0)
curl "localhost:8002/runs/compare?base=1&candidate=2"
# -> {"verdict": "block", "summary": {"regressed": 2, "still_passing": 1, ...}}
```

## Using the real Claude API

Set `LLM_PROVIDER=anthropic` and `LLM_API_KEY` in `.env` and restart evals. The SDK retries rate limits (429) and server errors (5xx) up to 3 times with exponential backoff; a refused request is recorded as an `error` result for that test case and the rest of the run continues. The deployed system uses the fake provider.

## Project layout

```
docker-compose.yml        the whole system locally
db/init.sql               creates both databases and each service's login (compose only)
system.yaml               machine-readable system description (+ system.schema.json)
services/
  prompts/                Dockerfile, requirements*.txt, openapi.yaml, migrations/, app/, tests/
  evals/                  Dockerfile, requirements*.txt, openapi.yaml, migrations/, app/, tests/
ui/                       static UI; config.js holds the service URLs
tests/integration/        cross-seam test against the running compose stack
.github/workflows/        ci.yml (every push and PR), deploy.yml (main only)
docs/DESIGN.md            system design
ADR.md, AI_USAGE.md       decision records and AI usage log
```
