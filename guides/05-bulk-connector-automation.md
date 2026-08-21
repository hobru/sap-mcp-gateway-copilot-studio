# MCP Gateway on SAP Integration Suite — bulk connector automation for Copilot Studio MCP tools

Create **all 21** Power Platform custom connectors for the SAP **MCP Gateway** endpoints in one automated pass — each connector surfaces as an **MCP tool** in **Microsoft Copilot Studio**. Instead of running the connector wizard 21 times and hand-patching the C# code step every time (the manual flow from Parts 2–3), you scaffold the connector definitions once and deploy them with `pac connector create`, which sets the **SAP IAS** OAuth configuration **and** embeds the custom C# script in a **single call**.

This builds directly on **Part 3** ([guide](./03-sap-ias.md) · [video](https://youtu.be/7Y4TH2DWIoo)). The identity chain does not change: users still sign in through **Entra ID federated into IAS**, and every connector validates the **IAS-issued** token. What changes is **how many connectors you create and how you create them** — Part 3 wired up **one** connector by hand; Part 5 scales that exact pattern to **many**, unattended.

| | Part 3 (single connector, manual) | This guide (bulk, automated) |
|---|---|---|
| How the connector is created | Copilot Studio **custom-connector wizard** | `pac connector create` (Power Platform CLI) |
| OAuth (SAP IAS) config | typed into the wizard | written into `apiProperties.json`, applied by the CLI |
| Content-Type fix | **manually** enable Code → paste `custom-connector-script.csx` → Update | embedded via `--script-file` in the **same** create call |
| Number of connectors | 1 | **21** (Sales, Finance, Procurement) |
| Client secret | typed into the wizard | entered **only at runtime** via a secure prompt — never stored |

> The MCP Gateway is one of two architectures explicitly **endorsed by SAP** in the [SAP API Policy](https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf). Automating connector creation changes nothing about the identity chain or the endpoints — it only removes the repetitive manual clicks.

---

## Why automate?

The Part 3 flow is fine for one connector. For a full SAP surface it does not scale: each endpoint means re-running the wizard, re-typing the same IAS OAuth values, and re-doing the **enable Code → paste script → Update** dance that fixes the `Content-Type: application/json; charset=utf-8` rejection. Twenty-one endpoints is twenty-one chances to fumble a redirect, a scope, or a script paste.

`pac connector create` collapses all of that into one command per connector:

1. **Creates** the custom connector from a generated `apiDefinition` (OpenAPI) + `apiProperties` (OAuth) pair.
2. **Configures OAuth** against **SAP IAS** — authorize/token URLs, scope, client id — from `apiProperties.json`.
3. **Embeds** the C# fix (`custom-connector-script.csx`) via `--script-file`, so the strict-equality `Content-Type` patch is applied **at create time** — no manual Code step.

Two small helper scripts drive it: **`Generate-Connectors.py`** scaffolds the definitions for all 21 endpoints, and **`Deploy-Connectors.ps1`** runs `pac connector create` for one, a group, or all of them, prompting for the IAS client secret securely.

---

## The 21 endpoints

Every connector points at one MCP Gateway endpoint on Integration Suite. The URL follows a single pattern:

```
https://<integration-host>/<CONNECTOR_NAME>
```

Use `<integration-host>` as the placeholder for your Integration Suite runtime host. In this walkthrough the example host is:

```
mcaps-xxxxxxxx-cloud.sap
```

The endpoints group into three functional areas:

**Sales (7)**

| Connector name | Endpoint |
|---|---|
| `MCP_SALES_BUSINESS_PARTNER` | `https://<integration-host>/MCP_SALES_BUSINESS_PARTNER` |
| `MCP_SALES_CUSTOMER_RETURN_SRV` | `https://<integration-host>/MCP_SALES_CUSTOMER_RETURN_SRV` |
| `MCP_SALES_OUTBOUND_DELIVERY_SRV` | `https://<integration-host>/MCP_SALES_OUTBOUND_DELIVERY_SRV` |
| `MCP_SALES_PRODUCT_SRV` | `https://<integration-host>/MCP_SALES_PRODUCT_SRV` |
| `MCP_SALES_SALES_INQUIRY_SRV` | `https://<integration-host>/MCP_SALES_SALES_INQUIRY_SRV` |
| `MCP_SALES_SALES_ORDER_SRV` | `https://<integration-host>/MCP_SALES_SALES_ORDER_SRV` |
| `MCP_SALES_SALES_QUOTATION_SRV` | `https://<integration-host>/MCP_SALES_SALES_QUOTATION_SRV` |

**Finance (6)**

| Connector name | Endpoint |
|---|---|
| `MCP_FIN_CHARTOFACCOUNTS_SRV` | `https://<integration-host>/MCP_FIN_CHARTOFACCOUNTS_SRV` |
| `MCP_FIN_GLACCOUNTINCHARTOFACCOUNTS_SRV` | `https://<integration-host>/MCP_FIN_GLACCOUNTINCHARTOFACCOUNTS_SRV` |
| `MCP_FIN_GLACCOUNTLINEITEM` | `https://<integration-host>/MCP_FIN_GLACCOUNTLINEITEM` |
| `MCP_FIN_JOURNALENTRYITEMBASIC_SRV` | `https://<integration-host>/MCP_FIN_JOURNALENTRYITEMBASIC_SRV` |
| `MCP_FIN_OPLACCTGDOCITEMCUBE_SRV` | `https://<integration-host>/MCP_FIN_OPLACCTGDOCITEMCUBE_SRV` |
| `MCP_FIN_SUPPLIERINVOICE_PROCESS_SRV` | `https://<integration-host>/MCP_FIN_SUPPLIERINVOICE_PROCESS_SRV` |

**Procurement (8)**

| Connector name | Endpoint |
|---|---|
| `MCP_PROC_INFORECORD_PROCESS_SRV` | `https://<integration-host>/MCP_PROC_INFORECORD_PROCESS_SRV` |
| `MCP_PROC_PURCHASECONTRACT_PROCESS_SRV` | `https://<integration-host>/MCP_PROC_PURCHASECONTRACT_PROCESS_SRV` |
| `MCP_PROC_PURCHASEORDER_PROCESS_SRV` | `https://<integration-host>/MCP_PROC_PURCHASEORDER_PROCESS_SRV` |
| `MCP_PROC_PURCHASEREQ_PROCESS_SRV` | `https://<integration-host>/MCP_PROC_PURCHASEREQ_PROCESS_SRV` |
| `MCP_PROC_QTN_PROCESS_SRV` | `https://<integration-host>/MCP_PROC_QTN_PROCESS_SRV` |
| `MCP_PROC_RFQ_PROCESS_SRV` | `https://<integration-host>/MCP_PROC_RFQ_PROCESS_SRV` |
| `MCP_PROC_SERVICE_ENTRY_SHEET_SRV` | `https://<integration-host>/MCP_PROC_SERVICE_ENTRY_SHEET_SRV` |
| `MCP_PROC_SUPPLIERINVOICE_PROCESS_SRV` | `https://<integration-host>/MCP_PROC_SUPPLIERINVOICE_PROCESS_SRV` |

Each connector is titled with a consistent convention so it reads cleanly in the Copilot Studio tool list:

```
SAP {Area} - {Entity} - MCP
```

For example, `SAP Sales - Sales Order - MCP` or `SAP Procurement - Purchase Order - MCP`.

---

## Importable example packages

Three ready-made **SAP Integration Suite content packages** live in [`../integration-packages/`](../integration-packages/). They map **1:1 to the 21 endpoints** above — Sales (7), Finance (6), Procurement (8) — so you can stand up the MCP Gateway side quickly before you create the connectors:

| Package | Flows | Area |
|---|---|---|
| [`BPS-Agents-Sales.zip`](../integration-packages/BPS-Agents-Sales.zip) | 7 | Sales |
| [`BPS-Agents-Finance.zip`](../integration-packages/BPS-Agents-Finance.zip) | 6 | Finance |
| [`BPS-Agents-Procurement.zip`](../integration-packages/BPS-Agents-Procurement.zip) | 8 | Procurement |

Import each package via **Integration Suite → Design → Integrations and APIs → (Actions) → Import integration package**, then deploy the flows. Each deployed flow is one MCP Gateway endpoint, fronted by one of the connectors below. See [`integration-packages/README.md`](../integration-packages/README.md) for the full flow list and import steps.

---

## Prerequisites

- The **Part 3 setup** working end to end: Copilot Studio → Entra ID → **IAS** → MCP Gateway validating the IAS-issued token and reading `mail`. See the [IAS guide](./03-sap-ias.md).
- The **21 MCP Gateway endpoints** deployed on Integration Suite (the connectors just front them).
- The **Power Platform CLI** (`pac`) installed and authenticated (`pac auth create`). `pac connector create` is the workhorse.
- **Python 3** to run `Generate-Connectors.py`, and **PowerShell** to run `Deploy-Connectors.ps1`.
- The **SAP IAS App-2** client from Part 3 (the OAuth client Copilot Studio uses) — its **client id** and **client secret**.

---

## OAuth configuration (SAP IAS)

Every connector uses the **same** SAP IAS OAuth 2.0 (authorization code) configuration — identical to Part 3, just written into `apiProperties.json` instead of typed into the wizard:

| Setting | Value |
|---|---|
| Authorization URL | `https://myXXXXXX.accounts.ondemand.com/oauth2/authorize` |
| Token URL | `https://myXXXXXX.accounts.ondemand.com/oauth2/token` |
| Refresh URL | `https://myXXXXXX.accounts.ondemand.com/oauth2/token` |
| Scope | `openid email profile offline_access` |
| Power Platform environment | `00000000-0000-0000-0000-000000000000` (BPS Agent Hub) |
| Client id | `11111111-1111-1111-1111-111111111111` |
| Client secret | **entered at runtime only** — via the `Deploy-Connectors.ps1` secure prompt |

Notes:

- **`offline_access` is required.** It is what makes IAS return a **durable refresh token** so Copilot Studio can refresh the connection silently (the same *"Refresh Token missing"* gotcha called out in Part 3). IAS has no custom scopes, so the scope list stays within `openid email profile offline_access`.
- The **client id** is not a secret and may appear in the generated `apiProperties.json`.
- The **client secret is a secret.** It is **never** written to a file, hard-coded, or committed. `Deploy-Connectors.ps1` prompts for it securely at deploy time and passes it straight to `pac connector create`.

> **Secret hygiene:** if you fork these scripts, keep the secret out of source control. The generated `apiProperties.json` carries the client **id** only; the secret lives in your head (or a vault) until the secure prompt.

---

## How it works

The automation is two steps: **generate**, then **deploy**.

### 1 · Generate the connector definitions

```bash
python scripts/Generate-Connectors.py
```

`Generate-Connectors.py` produces, for each of the 21 endpoints, the trio of files `pac connector create` expects:

- **`apiDefinition`** — the OpenAPI definition for the connector's operations (pointed at `https://<integration-host>/<CONNECTOR_NAME>`).
- **`apiProperties.json`** — the SAP IAS OAuth block (authorize/token/refresh URLs, `openid email profile offline_access` scope, client id) — **no secret**.
- **`settings.json`** — the Power Platform environment and per-connector metadata (title `SAP {Area} - {Entity} - MCP`).

### 2 · Deploy with `pac connector create`

`Deploy-Connectors.ps1` runs `pac connector create` for each selected connector. In a **single** call it:

- creates the custom connector from the generated `apiDefinition` + `apiProperties`,
- applies the **SAP IAS** OAuth configuration, and
- embeds the C# fix via `--script-file scripts/custom-connector-script.csx` — so the `Content-Type` patch is baked in at create time, **replacing** the manual *enable Code → paste → Update* step from Parts 2–3.

Deploy one connector:

```powershell
./scripts/Deploy-Connectors.ps1 -Environment 00000000-0000-0000-0000-000000000000 -Only MCP_SALES_SALES_ORDER_SRV
```

Deploy a whole area:

```powershell
./scripts/Deploy-Connectors.ps1 -Environment 00000000-0000-0000-0000-000000000000 -Area Procurement
```

Deploy into a specific solution, or all 21 at once:

```powershell
# all 21, grouped into a solution
./scripts/Deploy-Connectors.ps1 -Environment 00000000-0000-0000-0000-000000000000 -Solution SapMcpConnectors
```

`-Only` targets a single connector, `-Area` a functional group (Sales / Finance / Procurement), and `-Solution` bundles the connectors into a Power Platform solution; with none of the filters it processes **all 21**. In every case the script **prompts for the IAS client secret securely** (a masked prompt) and passes it to `pac connector create` — the secret is never echoed, stored, or committed.

---

## Redirect URLs

Because the **SAP IAS App-2** application registers the **`/**` wildcard redirect** (`https://global.consent.azure-apim.net/redirect/**`, as set up in Part 3), it already matches **every** connector's connection-specific redirect. That means:

- **No per-connector redirect registration is required.** The wildcard covers all 21 connectors and any connection you recreate later.

`Collect-Redirects.ps1` is an **optional** helper for the case where you are **not** using the wildcard: it lists each connector's redirect URL so you can add them to the IAS app individually. If you kept the Part 3 wildcard, you can ignore it.

---

## Two residual manual steps

Automation covers connector creation end to end. Two steps still need a human, and neither is repetitive script-paste work:

1. **(Only if you are *not* using the wildcard redirect)** add each connector's redirect URL to the **SAP IAS App-2** application under **Single Sign-On → OpenID Connect Configuration → Redirect URIs**. With the Part 3 `/**` wildcard this step is unnecessary.
2. **Add each connector as a tool to the Copilot Studio agent.** There is **no public API** for attaching a connector to an agent yet, so you add the created connectors as MCP tools in the Copilot Studio maker UI. Creation is automated; the final "make it a tool of *this* agent" wiring is still a click.

---

## Where this leaves you

- **Part 3** gave you one connector and the full IAS identity chain.
- **Part 5** reuses that exact chain and scales it to the whole SAP surface — 21 connectors, created unattended, each carrying the `Content-Type` fix and the IAS OAuth config, with the client secret supplied only through a secure runtime prompt.

Once the connectors are created and added as tools, the Copilot Studio agent can reason across Sales, Finance, and Procurement MCP tools — every call still running under the signed-in user's **IAS** identity, ready for on-prem **principal propagation** exactly as in [Part 4](./04-principal-propagation.md).

---

## Supporting artifacts

- [`Generate-Connectors.py`](../scripts/Generate-Connectors.py) — generates the per-connector `apiDefinition` / `apiProperties` / `settings` files for all 21 endpoints.
- [`Deploy-Connectors.ps1`](../scripts/Deploy-Connectors.ps1) — bulk `pac connector create` with `-Only` / `-Area` / `-Solution` selectors and a secure IAS client-secret prompt.
- [`Collect-Redirects.ps1`](../scripts/Collect-Redirects.ps1) — optional helper that lists each connector's redirect URL (only needed when the IAS `/**` wildcard redirect is not used).
- [`custom-connector-script.csx`](../scripts/custom-connector-script.csx) — the C# `Content-Type` fix, embedded into each connector via `--script-file` at create time.
