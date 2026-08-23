# Your own ABAP MCP server (`zmcp2`) with end-to-end SSO — via the BTP Router app

> 🎬 **Watch:** [Copilot Studio & SAP — Your Own ABAP MCP Server (zmcp2) via the BTP Router](https://youtu.be/az4TIbpmMFI)

Instead of generating MCP tools from OData in the Integration Suite MCP Gateway, this part runs the **MCP server itself inside your ABAP system** — using the open-source **ABAP Model Context Protocol Server SDK v2** ([`abap-ai/mcp2`](https://github.com/abap-ai/mcp2)) — and fronts it with the lightweight **BTP Router app** ([`hobru/CAP-Routing-App`](https://github.com/hobru/CAP-Routing-App)) for **end-to-end single sign-on** into **Microsoft Copilot Studio**.

The SDK lets you expose *any* data or logic in your ABAP system as MCP tools with a few classes. The BTP Router adds the **SAP IAS (federated to Microsoft Entra ID) → Cloud Connector → short-lived X.509 → real ABAP user** identity chain on top — so each tool call runs as the **signed-in user**, not a shared technical account. Together they are an amazingly fast way to get a **production-shaped, enterprise-ready SSO** MCP scenario running.

> The BTP Router is protocol-agnostic and can front almost **any** on-premise SAP HTTP endpoint (MCP, plain OData, any HTTP API). Here it fronts an ABAP MCP server built with `zmcp2`.

---

## Positioning — relative to the MCP Gateway (Parts 1–5)

| | Parts 1–5 — MCP Gateway (Integration Suite) | Part 6 — ABAP MCP server + BTP Router |
|---|---|---|
| Where the MCP server runs | On **Integration Suite**, generated from an **OData** OpenAPI spec | **Inside ABAP**, hand-authored with the `zmcp2` SDK |
| What exposes the tools | The Integration Suite MCP Gateway flow | Your own ABAP classes (`define_tools` / `call_tool`) |
| Cloud front door | Integration Suite (rate limiting, quotas, analytics) | **CAP BTP Router** (minimal auth + routing proxy) |
| Identity chain | SAP IAS → Cloud Connector → X.509 → real ABAP user | **Same** chain — reused via the BTP Router |
| Best for | Productised, policy-governed API surface | **Trial / PoC / simple** scenarios, fast to stand up |

The MCP Gateway remains one of two architectures explicitly **endorsed by SAP** in the [SAP API Policy](https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf). The BTP Router follows the **same principal-propagation approach** with fewer moving parts — a great way to pilot quickly, then graduate to the MCP Gateway when the use case hardens.

---

## The two repos you need

| Repo | Role |
|---|---|
| [`abap-ai/mcp2`](https://github.com/abap-ai/mcp2) | The **ABAP MCP Server SDK v2** (`zmcp2`). Stateless, Streamable HTTP, protocol `2026-07-28` (legacy-compatible). Installed via **abapGit** in your ABAP system. |
| [`abap-ai/mcp2-702`](https://github.com/abap-ai/mcp2-702) | The **7.02 – 7.4x downport** of the SDK, if you are on an older NetWeaver stack. |
| [`hobru/CAP-Routing-App`](https://github.com/hobru/CAP-Routing-App) | The **BTP Router app** (CAP / Node.js on Cloud Foundry) — an IAS-authenticated, principal-propagating reverse proxy from Copilot Studio to your on-prem endpoints. |

> `zmcp2` ships **no default auth check** — you implement your own if needed (see the SDK's [Configuration and security](https://github.com/abap-ai/mcp2/blob/main/docs/ConfigurationAndSecurity.md)). In this scenario, authentication and SSO are handled **in front** of ABAP by the BTP Router (IAS) and principal propagation, and the tool runs as the mapped ABAP user.

---

## How it works

```
Copilot Studio / Teams ──HTTPS + Bearer(IAS)──▶ BTP Router (CAP, Cloud Foundry)
        Entra ID ──▶ IAS (OIDC access token)
                                    │
                                    ▼  connectivity proxy (principal propagation)
                             SAP Cloud Connector ──short-lived X.509──▶ ABAP
                                                                          │
                                                          zmcp2 MCP server (/sap/zmcp2)
                                                     tools run as the mapped SU01 user
```

1. **Copilot Studio** (or Teams/Copilot) calls the **BTP Router** URL with an IAS bearer token.
2. The **BTP Router** obtains/validates the token via **SAP IAS**, which federates authentication to **Microsoft Entra ID**.
3. The router forwards through the **SAP Cloud Connector**, which mints a **short-lived X.509 certificate** for the user and calls the on-prem ABAP system.
4. The **`zmcp2` MCP server** on the ABAP stack (e.g. `/sap/zmcp2`) executes the tool — a simple `SELECT`, an `UPDATE`, or anything you implement — **as the real, mapped ABAP user** (via `CERTRULE` email mapping), and returns the result all the way back to the client.

---

## Building the ABAP MCP server (`zmcp2`)

From the video, standing up an MCP tool server is a few small steps:

1. **Install the SDK** via **abapGit** from [`abap-ai/mcp2`](https://github.com/abap-ai/mcp2) (or [`mcp2-702`](https://github.com/abap-ai/mcp2-702) on 7.02–7.4x).
2. **Register the ICF service/handler** for `zmcp2` so requests reach the SDK runtime.
3. **Author a tool server** — inherit from the SDK's tool-server base and implement:
   - `define_tools( )` — declare the tools (e.g. *list flights*, *update flight*) and their input schemas (required properties like carrier id, max rows).
   - `call_tool( )` — the handler logic (e.g. a `SELECT` to list, a `SELECT` + `UPDATE` to change a flight) that returns typed results to the base class.

The video's demo `SFLIGHT` tool server does exactly this, plus a `greeter` sample tool that simply returns the **logged-on user name** — which makes the SSO / principal-propagation result visible end to end (the call runs as the mapped SAP user, e.g. `developer`).

---

## Fronting it with the BTP Router

1. **Clone and deploy** the [BTP Router](https://github.com/hobru/CAP-Routing-App) to Cloud Foundry (`mbt build` → `cf deploy`). The deploy **automatically creates the SAP IAS entries** that form the SSO foundation, plus destination/connectivity/identity/logs services.
2. **Verify** the router is up: `GET /health` (status + build info) and `GET /config` (resolved routes → destination + backend path). The router supports **multiple destinations**, so one router can front several SAP systems.
3. **Point a route at the ABAP MCP server** — e.g. map `/ZMCP2` → `/sap/zmcp2` on the backend, through an **OnPremise + PrincipalPropagation** destination (`NPLSSL`) that reaches your ABAP system via the **Cloud Connector**.
4. **Connect from Copilot Studio** — add a custom/MCP connection to the router URL (`…/ZMCP2/demo/greeter`) with the **same OAuth 2.0 (IAS) settings** used to test in Bruno. Add the tool to your agent, then preview it (e.g. "hi there") — the tool is called **in your user context**.

A quick **Basic-authentication** call straight to the ABAP endpoint (`/sap/zmcp2/demo/greeter`) is a useful baseline before flipping the destination to **Principal Propagation** and routing through the BTP Router.

---

## 🎬 Video index

| Time | Topic |
|---|---|
| 00:00 | What this is — the BTP Router app + the ABAP MCP Server SDK (`zmcp2`) |
| 00:47 | The finished scenario, tested from a REST client (Bruno) |
| 01:17 | Installing `zmcp2` in SAP via abapGit and registering the ICF handler |
| 02:02 | Building the demo `SFLIGHT` tool server (`define_tools`: list & update) |
| 02:31 | Tool input schemas — the required properties |
| 02:50 | Handler classes — `SELECT` to list, `SELECT` + `UPDATE` to change a flight |
| 03:27 | Bundling the MCP server with the BTP Router for end-to-end SSO |
| 03:54 | The `greeter` tool runs as the logged-on user — proven in Bruno |
| 04:35 | How it was built: cloning and deploying the BTP Router |
| 05:09 | Deploy auto-creates the IAS entries; health check and `/config` |
| 05:46 | Multiple destinations — mapping `/ZMCP2` to the on-prem system |
| 06:22 | The `NPLSSL` destination → Cloud Connector → principal propagation |
| 06:43 | Direct Basic-auth call to the on-prem greeter (baseline) |
| 07:08 | The same call through the BTP Router with the IAS access token |
| 07:51 | Connecting the MCP server in Copilot Studio (OAuth 2.0 settings) |
| 08:36 | Adding the `greeter` tool and testing "hi there" as the real user |
| 09:04 | Why this is a fast path to enterprise-ready SSO |
| 09:23 | The end-to-end identity flow, recapped |

---

## Where this leaves you

- **Parts 1–5** exposed SAP through the **Integration Suite MCP Gateway**, generated from OData.
- **Part 6** flips it: the **MCP server runs in your ABAP system** (`zmcp2`), and the **BTP Router** supplies the same **SAP IAS → Cloud Connector → X.509 → real ABAP user** SSO in front of it.

The result is a minimal, fast-to-deploy path to a **user-context** MCP scenario in Copilot Studio (and Teams/Copilot) — ideal for a trial, proof of concept, or a simple production scenario — that you can later graduate to the full MCP Gateway when you need rate limiting, quotas, and API analytics.

---

## Supporting repos & docs

- [`abap-ai/mcp2`](https://github.com/abap-ai/mcp2) — the ABAP MCP Server SDK v2 (`zmcp2`), with [docs](https://github.com/abap-ai/mcp2/tree/main/docs) (protocol support, configuration & security, server authoring).
- [`abap-ai/mcp2-702`](https://github.com/abap-ai/mcp2-702) — the 7.02–7.4x downport of the SDK.
- [`hobru/CAP-Routing-App`](https://github.com/hobru/CAP-Routing-App) — the BTP Router app, with its own [setup walkthrough](https://youtu.be/xbBXcF79qyY) and [architecture](https://github.com/hobru/CAP-Routing-App/blob/main/docs/architecture.md) / [BTP & backend setup](https://github.com/hobru/CAP-Routing-App/blob/main/docs/btp-backend-setup.md) docs.
- [Model Context Protocol](https://modelcontextprotocol.io/) — the MCP specification (Streamable HTTP transport).
