# MCP Gateway on SAP Integration Suite — your own backend with principal propagation

Connect **Microsoft Copilot Studio** to **your own on-premise SAP system** through the **MCP Gateway** on Integration Suite — first with a quick **Basic Authentication** foil, then with **end-to-end principal propagation** so every backend OData call runs as the **real ABAP user** behind the Copilot Studio identity.

📺 **Watch the video:** _link to follow_

This is **Phase 2** of *"MCP Gateway — user authentication with SAP Cloud Identity Services (IAS), federated to Microsoft Entra ID"* ([guide](./03-sap-ias.md)). The **front end does not change**: users still sign in through **Entra ID federated into IAS**, and the MCP Gateway still validates the **IAS-issued** token and reads the user's **`mail`** claim. What changes is the **backend**: instead of the anonymous **SWAPI** (Star Wars API) call we now invoke **our own on-prem SAP OData service** (`API_BUSINESS_PARTNER`) through a **Cloud Connector**, and we make the backend run as the **real end user**.

| | Previous video (IAS — Phase 1) | This video (Phase 2) |
|---|---|---|
| Backend | **SWAPI** (Star Wars API), external | **Your own on-prem SAP** (`API_BUSINESS_PARTNER`) |
| Backend reachability | public internet | **Cloud Connector** + BTP **Destination** |
| Backend auth (step 1) | **anonymous** (no credentials) | **Basic Authentication** (one technical user) |
| Backend auth (final) | — | **Principal propagation** (X.509, per-user) |
| Who the OData call runs as | nobody (anonymous) | the **real ABAP user** of the signed-in person |
| Front-end identity | Entra ID → IAS (`mail`) | **unchanged** — Entra ID → IAS (`mail`) |

> The MCP Gateway is one of two architectures explicitly **endorsed by SAP** in the [SAP API Policy](https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf). Principal propagation to a private OData service is a **Documented Use** of a published API, so this pattern stays inside the policy.

---

## Architecture

```
Copilot Studio ─▶ MCP Gateway (Integration Suite / Integration Cell) ─▶ BTP Destination ─▶ Cloud Connector ─▶ on-prem SAP
  (end user)        validates IAS token, reads `mail`,                    PrincipalPropagation    mints a short-lived        ICM (mutual TLS)
                    forwards it as SAP-Connectivity-Authentication         (X.509)                per-user X.509 cert         + CERTRULE → real ABAP user
```

- **Front end (unchanged):** Copilot Studio → Entra ID OAuth → **IAS** token exchange → MCP Gateway validates the IAS JWT and reads the user's **`mail`**.
- **BTP Destination:** an **OnPremise** destination whose `Authentication` starts as **BasicAuthentication** (Part A) and is later switched to **PrincipalPropagation** (Part B). Only this one property changes between the two parts.
- **Cloud Connector (CC):** exposes the on-prem SAP system under an internal **virtual host**. For principal propagation it mints a **short-lived per-user X.509 certificate** (subject = the user's `mail`), signed by its **Principal Propagation CA**, and presents its own **System Certificate** to the backend over mutual TLS.
- **On-prem SAP (ICM + ABAP):** trusts the CC as a **trusted reverse proxy**, accepts the forwarded per-user certificate, and maps it to an ABAP user with **rule-based certificate mapping (CERTRULE)** on the `E-Mail` attribute.

---

## Environment values used in this walkthrough

> Real identifiers below are **masked** — only the first and last few characters are shown (e.g. `bb959…68840`). Passwords, client secrets and tokens are never shown. Replace everything with your own values.

| Thing | Value (masked) |
|---|---|
| Backend SID / client | `PM4` / `400` |
| CC virtual host (HTTPS + X.509) | `pm4.internal.ssl:44301` |
| Backend real host (FQDN) | `micro…o.com` |
| Subaccount ID | `bb959…68840` |
| Subaccount subdomain | `8e140…trial` |
| IAS tenant host | `adhbc…d.com` |
| Cloud Connector version | **2.19.1** (System Certificate needs **≥ 2.7.0**) |
| CC Principal Propagation CA | `CN=Cloud Connector Principal Propagation CA` |
| CC System Certificate | `CN=SCC-8e140…trial` |
| Location ID | `PM4-Trial` |
| Example users (email → ABAP) | `hobru…t.com` → `HOBR…CHE` · `BPSAd…t.com` → `HOBR…-TST` |

---

## Two ways to reach the backend

We build this in **two parts**, each independently testable:

- **Part A — Basic Authentication (the 60-second foil).** Point the Destination at the Cloud Connector with a **single technical user** and Basic Auth. This proves the *whole path* (Copilot Studio → MCP Gateway → Destination → CC → SAP OData) with the least moving parts. Every OData call runs as that one technical user.
- **Part B — Principal propagation (the goal).** Flip the Destination to **PrincipalPropagation** and add the SAP-side trust so the backend runs as the **real end user**. This is where all the SAP configuration lives.

Do Part A first. If Part A fails, principal propagation cannot work either — you'd just be debugging two problems at once.

---

## ⚠️ Prove the "bridge" first

Everything in Part B depends on **one** thing: the MCP Gateway must **forward the inbound IAS token** into the PrincipalPropagation destination call, so the Connectivity Proxy receives a `SAP-Connectivity-Authentication` header it can turn into a per-user certificate.

Before you touch STRUST, CERTRULE or profile parameters, confirm the gateway forwards the token. If it does not, no amount of ABAP trust configuration will help — the Cloud Connector has nothing to mint a certificate from.

---

## Prerequisites

- The **previous video's setup** working end to end: Copilot Studio → Entra ID → **IAS** → MCP Gateway validating the IAS-issued token and reading `mail`. See the [IAS guide](./03-sap-ias.md).
- An **on-prem (or IaaS) SAP system** exposing an OData service — here **`API_BUSINESS_PARTNER`** on `PM4` client `400`.
- A **Cloud Connector** (**2.7.0+**, this walkthrough used 2.19.1) installed and able to reach the SAP system, connected to your BTP subaccount.
- Rights on the SAP system for **STRUST**, **CERTRULE**, **RZ10**, **SMICM**, **SU01**, and to **restart** the system.
- **SAP Cloud Identity Services (IAS)** already trusted by the subaccount (from the previous video).
- VS Code with the **REST Client** extension (optional, for testing).

---

# Part A — Basic Authentication foil

Goal: reach the on-prem OData service through the Cloud Connector with the fewest moving parts.

### A1 · Cloud Connector — expose the backend (HTTPS + X.509)

In the Cloud Connector, under **Cloud To On-Premise → Access Control**, add the backend system **once** — you use the *same* mapping for the Basic-Auth foil now and for principal propagation in Part B:

- **Back-end type:** ABAP System
- **Protocol:** **HTTPS** *(deliberate — HTTPS is what lets the Cloud Connector present a short-lived per-user certificate in Part B)*
- **Internal host:** `micro…o.com` · **port** `44301`
- **Virtual host:** `pm4.internal.ssl` · **port** `44301`
- **Principal Type:** **X.509 Certificate (General Usage)**
- Expose the resource paths you need — here `/sap/opu/odata` **and** `/sap/bc` (path **and** sub-paths). *(On a trial system this is permissive; be more restrictive in production.)*

> **First check says *"not reachable — issuer not trusted"*?** Expected under HTTPS — the Cloud Connector doesn't yet trust your SAP system's **server** certificate. Import it under **Configuration → On-Premise → Back-End Trust Store** (download the ICM server certificate from the SAP system, upload it here, save), then re-run the check — it must go green.

### A2 · BTP Destination — OnPremise + Basic Auth

Create (or reuse) a **Destination** in the subaccount:

| Property | Value |
|---|---|
| `Type` | `HTTP` |
| `ProxyType` | `OnPremise` |
| `Authentication` | `BasicAuthentication` |
| `URL` | `https://pm4.internal.ssl:44301` |
| `User` / `Password` | a **technical** ABAP user (masked) |
| `sap-client` (URL or header) | `400` |
| `CloudConnectorLocationId` | `PM4-Trial` |

Add one **Additional Property** so the destination surfaces in the MCP server builder: set the *Integration Cell include* flag to `true`.

Use **Check Connection** in the Destination editor — it must be green.

### A3 · Point the MCP Gateway at the Destination

In your MCP Server integration flow, set the OData receiver to call **through the destination** (`https://pm4.internal.ssl:44301/sap/opu/odata/sap/API_BUSINESS_PARTNER/...`). Nothing on the **front end** changes — Copilot Studio, Entra ID and IAS are exactly as in the previous video.

Ask the agent *"show me 5 business partners"* — you should get real rows from your own system.

### A4 · Confirm the call really went through the Cloud Connector

<details>
<summary>Optional — verify the path (CC Monitor + gateway trace)</summary>

- **CC → Monitoring → Most Recent Requests**: you should see the request to `pm4.internal.ssl:44301` with the **technical user**.
- **SAP `/IWFND/TRACES`** (or `/IWFND/ERROR_LOG`): the executing user is the **technical user** — this is the expected limitation of Basic Auth and the reason we move to Part B.

> In Part A **every** end user shows up as the same technical backend user. That's the whole point of the foil: prove connectivity now, add identity in Part B.
</details>

---

# Part B — Principal propagation (run as the real user)

Now we make the backend OData call execute as the **real ABAP user** behind the Copilot Studio identity. The front end still doesn't change — we only add **trust** on the SAP/CC side and flip **one** destination property.

> **The mental model.** The Cloud Connector receives the user's identity (from the forwarded IAS token) and mints a **short-lived X.509 certificate** whose **subject = the user's email**. It presents this per-user certificate to the SAP ICM over **mutual TLS**, together with its own **System Certificate** that proves *"I am a trusted reverse proxy"*. ICM keeps the forwarded per-user certificate and hands it to the ABAP work process, which uses **CERTRULE** to map `E-Mail → ABAP user`.

There are exactly **three** things to get right, and they are the three that cost the most time:

1. **Mutual TLS actually completes** (CC ↔ ICM) — needs the CC CA and CC System Certificate trusted in the **SSL server** PSE, plus `icm/HTTPS/verify_client=1`.
2. **ICM keeps the forwarded certificate** — needs `icm/trusted_reverse_proxy_<x>` pointing at the CC System Certificate.
3. **The certificate maps to a user at runtime** — needs `login/certificate_mapping_rulebased=1` **and a whole-system restart**, plus a CERTRULE rule.

Miss any one and you get a confusing error that looks like a different problem. The critical steps below are in order.

---

### B1 · Align the identity (do this first)

Principal propagation maps **email → ABAP user**, so the same email must be identical in three places:

- **Entra ID** sign-in (e.g. `hobru…t.com`)
- **IAS** user `mail`
- **SU01 → Address → E-Mail** of the target ABAP user (e.g. `HOBR…CHE`)

> If these don't match exactly, you'll get a backend logon failure even when every certificate is perfect. Set the SU01 email on each test user (`HOBR…CHE`, `HOBR…-TST`).

---

### B2 · Cloud Connector — the two certificates

The **HTTPS + X.509 mapping already exists from A1** — Part B doesn't add a new mapping, it adds the **two certificates** principal propagation needs. Confirm the existing mapping is:

- **Virtual host:** `pm4.internal.ssl:44301` · **Protocol:** **HTTPS** · **Principal Type:** **X.509 Certificate (General Usage)**
- **System Certificate for Logon (if no Principal is received):** **No** ✅ *(this is correct — the System Certificate is for trust/mutual-TLS only; the per-user short-lived certificate is what actually logs the user on).*

**Configure the two certificates** (this is the part most people miss). Since Cloud Connector 2.7.0, principal propagation uses **two** certificates:

| Certificate | Where | Purpose | Symptom if missing |
|---|---|---|---|
| **CA Certificate** | CC → *Configuration → On-Premise → Principal Propagation → CA Certificate* | signs the per-user leaf certificates | ICM never offers the CA in its TLS `CertificateRequest`; handshake picks no client cert |
| **System Certificate** | CC → *Configuration → On-Premise → System Certificate* | the CC's **own** client identity that proves *trusted reverse proxy* | CC sends an **empty** Certificate message → *"not mutually authenticated"* |

If the **System Certificate** shows *"No data"*, create a self-signed one (`CN=SCC-8e140…trial`). The CC **Connection Check** must then say *"System certificate acts as a client certificate"* with **no** issuer warning.

<details>
<summary>Why the System Certificate matters (CC ≥ 2.7.0 two-certificate model)</summary>

Before 2.7.0 a single certificate did both jobs. From 2.7.0 the CC splits them: the **CA** signs short-lived per-user certificates, while the **System Certificate** is the CC's own client credential presented in mutual TLS. The backend trusts the CC as a *reverse proxy* via the **System Certificate's issuer**, then trusts the *forwarded per-user certificate* separately. That's why a working setup needs **both** certificates trusted in the backend (next step), not just the CA.
</details>

---

### B3 · SAP ABAP — STRUST trust (the **SSL server** PSE)

In **STRUST**, import into **SSL server Standard** (`SAPSSLS.pse`) — **not** the SSL *client* PSE:

1. The **CC Principal Propagation CA** (`CN=Cloud Connector Principal Propagation CA`).
2. The **CC System Certificate's issuer** — because the System Certificate is self-signed, that's the System Certificate **itself** (`CN=SCC-8e140…trial`).

After importing, **restart ICM hard** (SMICM → *Administration → ICM → Exit Hard → Global*). A soft restart keeps cached credentials and the handshake won't pick up the new CA.

> **Why the *server* PSE?** ICM only advertises the CAs that live in its **SSL server** PSE inside the TLS `CertificateRequest`. If the CC CA is only in the SSL *client* PSE, the client (CC) is never asked for a certificate signed by it, and the per-user certificate is silently dropped.

<details>
<summary>Optional — verify ICM advertises the CA (security trace)</summary>

Raise the ICM trace (SMICM → *Goto → Trace Level → Set → 3*) and reproduce a call, then read the trace (SMICM → *Goto → Trace File → Display End*). A healthy handshake shows:

```
Accept trusted forwarded certificate subject="CN=BPSAd…t.com"
    issuer="CN=Cloud Connector Principal Propagation CA"
COPY_CERTHEADER_TO_MPI -> client cert copied to MPI
```

The failing state instead shows a line like *"intermediary is NOT trusted → remove SSL header fields"* — that means B3 or B4 is incomplete.
</details>

---

### B4 · SAP ABAP — three profile parameters (RZ10)

Set these in the **DEFAULT** profile (RZ10), then follow the restart note **exactly**:

| Parameter | Value | Purpose |
|---|---|---|
| `icm/HTTPS/verify_client` | `1` | ICM **requests** the client certificate (mutual TLS) |
| `icm/trusted_reverse_proxy_0` | `SUBJECT="CN=SCC-8e140…trial", ISSUER="CN=SCC-8e140…trial"` | ICM **keeps** (does not strip) the forwarded per-user cert from a trusted proxy |
| `login/certificate_mapping_rulebased` | `1` | CERTRULE rules are consulted **at runtime** (not only in the editor) |

> **This is the step that produced the mysterious 401.** With `login/certificate_mapping_rulebased` unset, the CERTRULE editor **simulates green**, ICM hands over the correct per-user certificate, but the ABAP runtime **ignores CERTRULE** and falls back to an empty external ID → **401 "Anmeldung fehlgeschlagen" for every user**. Because it's a 401 (authentication) — identical for a low-privilege and a high-privilege user — it is **not** a permissions problem.

> **Restart discipline.** `login/certificate_mapping_rulebased` only activates after a **whole-system restart** — an ICM-only restart is **not** sufficient (per SAP's own documentation). `icm/trusted_reverse_proxy_<x>` needs at least an **ICM Exit Hard (Global)**. Safest: set all three, then **restart the whole system once**.

---

### B5 · SAP ABAP — CERTRULE rule (email → user)

In transaction **`/nCERTRULE`**, create **one** rule (it serves all users):

| Field | Value |
|---|---|
| Certificate **Issuer** | `CN=Cloud Connector Principal Propagation CA` |
| Certificate **Entry** | `Subject` |
| **Attribute** | `CN` |
| **Login As** | `E-Mail` |
| **Subject Filter** | *(leave empty)* |

> **Don't use a `CN=*` subject filter** — CERTRULE rejects it, and it's unnecessary because the **issuer** already restricts the rule to certificates minted by your Cloud Connector CA.

<details>
<summary>Optional — validate the rule with a sample leaf certificate</summary>

If you load the **CA** certificate into the CERTRULE tester it always shows **red** ("certificate not mapped") — a CA has no email and isn't meant to map. To verify the rule, export a **sample per-user (leaf)** certificate from the Cloud Connector (*Principal Propagation → Sample certificate*) and test **that** — it should resolve to the SU01 user whose email matches the leaf's `CN`. `certrule` **success** on the sample leaf is your green light.
</details>

---

### B6 · Flip the Destination to PrincipalPropagation

The only front/BTP change in all of Part B — change **one** property on the Destination:

| Property | Part A | Part B |
|---|---|---|
| `Authentication` | `BasicAuthentication` | **`PrincipalPropagation`** |
| `User` / `Password` | technical user | *(remove)* |

The **URL stays the same** — `https://pm4.internal.ssl:44301` — because both parts use the one HTTPS virtual host you created in A1. Keep `ProxyType=OnPremise`, `CloudConnectorLocationId=PM4-Trial`, and `sap-client=400`.

---

### B7 · Verify it runs as the real user

Ask the agent *"show me 10 business partners"* as **two different signed-in users** and check the **Cloud Connector → Monitoring** *User* column — it must show the **two distinct propagated emails** resolving to the two ABAP users (`HOBR…CHE`, `HOBR…-TST`).

> **The first call is slow (~4 s).** That's the **cold certificate logon** (handshake + user context creation). Subsequent calls are fast — this is expected and production-safe.

> ⚠️ **`who am i` in Copilot Studio is *not* a valid backend-identity check.** It reflects the **Copilot/Entra** login, not the ABAP user. The authoritative signal is the **CC Monitor *User* column** (or `/IWFND/TRACES` / `sy-uname` in the backend).

---

## Troubleshooting quick reference

Most of the effort here is **pure SAP configuration** (Cloud Connector + ABAP), so here are the symptoms that cost the most time, with the fix:

| Symptom | Root cause | Fix |
|---|---|---|
| Copilot: *"Principal propagation forbidden … not mutually authenticated"*, CC shows **0 bytes** received, `/IWFND/TRACES` empty | Mutual TLS never completes | CC CA **and** System Certificate issuer imported into **SSL server** PSE (B3); CC **System Certificate** exists (B2); `icm/trusted_reverse_proxy_<x>` set (B4) |
| Backend **HTTP 401 "Anmeldung fehlgeschlagen"** for **all** users, but CERTRULE simulates green | `login/certificate_mapping_rulebased ≠ 1`, or no whole-system restart | Set `=1` (B4) + **restart the whole system** |
| CERTRULE shows **red / "certificate not mapped"** when you load the CA | Expected — a CA has no email | Test with a **sample leaf** certificate instead (B5) |
| CC Monitor shows the **technical** user, not the email | Destination still on **BasicAuthentication** | Flip to **PrincipalPropagation** (B6) |
| Backend logon fails though certs are perfect | Email mismatch across Entra / IAS / SU01 | Align the email in all three (B1) |
| Two test users on one PC show as the **same** backend user | Browser SSO / Windows account broker reusing one login | Use **InPrivate** / a different browser (see below) |

<details>
<summary>The full HTTPS handshake saga (findings we hit before mutual TLS worked)</summary>

Getting the HTTPS mapping (`pm4.internal.ssl:44301`) green in the Cloud Connector Connection Check required, in order:

1. **Right internal port** — the OData service listens on the ICM HTTPS port (`44301`), not the HTTP port.
2. **Backend certificate not expired** — an expired ICM server certificate fails the CC check; renew via STRUST + ICM restart.
3. **Cipher/curve compatibility** — the CC and ICM must agree on a cipher; an ECDSA-only backend certificate can break the negotiation. Prefer an RSA server certificate.
4. **CC trusts the backend CA** — import the backend's server CA into the CC trust store so the CC accepts the ICM's server certificate.
5. **SAN matches the internal host** — the backend server certificate's Subject Alternative Name must cover the internal host (`micro…o.com`).

Only after the **server**-side TLS was healthy did the **client**-side (per-user cert) work in B2–B5 become relevant.
</details>

<details>
<summary>Testing with two users on one machine (the "sticky user" trap)</summary>

While testing two users on **one** machine, both calls can show up as the **same** backend user even though you signed in as two different people. This is **not** a SAP or Cloud Connector problem — it's browser/OS identity caching:

- Two windows of the **same** browser profile share **one** cookie jar (one Entra/IAS session).
- Even **separate Edge profiles** can stay sticky because the **Windows account broker (WAM)** is machine-wide and silently hands out the primary work account **below** the profile's cookies. The tell is a **silent** sign-in with no credential prompt.

Fixes: use an **InPrivate/Incognito** window (it bypasses the broker), a **different browser**, or disable *"Allow single sign-on to work or school sites…"* in `edge://settings/profiles`. In production every user is on their own device, so this never occurs.

And again — verify identity with the **CC Monitor / `/IWFND/TRACES`**, never with `who am i` in Copilot Studio.
</details>

---

## Test the OData service directly (VS Code REST Client)

<details>
<summary>Optional — <code>principal-propagation.http</code> snippets</summary>

```http
### A. Basic Auth foil — direct OData through the Destination host (technical user)
GET https://micro…o.com:44301/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner?$top=2&sap-client=400
Authorization: Basic {{basic_b64}}
Accept: application/json

### B. MCP call with the IAS bearer token (principal propagation path)
# Paste a fresh IAS-issued token; the gateway forwards it and the backend runs as YOU.
POST https://<your-mcp-gateway-host>/mcp
Authorization: Bearer {{ias_token}}
Content-Type: application/json
Accept: application/json, text/event-stream

{ "jsonrpc": "2.0", "id": "1", "method": "tools/call",
  "params": { "name": "getBusinessPartners", "arguments": { "top": 5 } } }
```
</details>

---

## Appendix — Basic Authentication inline policy (Part A alternative)

<details>
<summary>Optional — put Basic Auth in the gateway instead of the Destination</summary>

If you prefer to keep credentials in the integration flow rather than the Destination, set the OData receiver to **Basic** and store the credential in a **Security Material** (User Credentials) artifact; reference it from the receiver. This keeps Part A entirely inside Integration Suite. It has the same limitation — every call runs as the one technical user — and is not compatible with principal propagation, so use it only for the foil.
</details>

---

## Appendix — Business Partner OpenAPI → MCP tools

The MCP tools in this walkthrough (`getBusinessPartners`, `getBusinessPartner`) come from an OpenAPI subset of `API_BUSINESS_PARTNER` — see [`api-business-partner-openapi.yaml`](../openapi/api-business-partner-openapi.yaml). Regenerate the MCP server from this spec exactly as in the first guide; only the **backend receiver** and **Destination** differ.

---

## Further reading — SAP principal propagation configuration

Because the hard part here is **pure SAP configuration** (Cloud Connector + ABAP trust), these are the references that actually unblock each step:

**Cloud Connector & principal propagation**
- Principal Propagation (SAP Connectivity) — <https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/principal-propagation>
- Configure Principal Propagation in the Cloud Connector — <https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/configure-cloud-connector-for-principal-propagation>
- Set up trust for principal propagation (CA + System Certificate) — <https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/set-up-trust-for-principal-propagation>
- Cloud Connector — Configure Access Control (virtual hosts) — <https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/configure-access-control-http>
- Initial Cloud Connector configuration & certificates — <https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/initial-configuration>

**ABAP / ICM trust (the parts that cost the most time)**
- Trusted reverse proxy — `icm/trusted_reverse_proxy_<xx>` — **SAP Note 3335949** — <https://me.sap.com/notes/3335949>
- Client certificate logon & rule-based mapping (`login/certificate_mapping_rulebased`, CERTRULE) — SAP Help (ABAP Platform → Security → Certificate Logon / rule-based mapping) — <https://help.sap.com/docs/ABAP_PLATFORM_NEW>
- ICM server parameters incl. `icm/HTTPS/verify_client` — SAP Help (ABAP Platform → Internet Communication Manager) — <https://help.sap.com/docs/ABAP_PLATFORM_NEW>
- Trust Manager (STRUST) / configuring AS ABAP for SSL — SAP Help (ABAP Platform → Security) — <https://help.sap.com/docs/ABAP_PLATFORM_NEW>
- Setting up mutual TLS / X.509 client-certificate logon (overview) — <https://community.sap.com/t5/technology-blog-posts-by-sap/x-509-client-certificate-authentication/ba-p/13512332>

**MCP Gateway & policy**
- SAP Reference Architecture — MCP Gateway — <https://architecture.learning.sap.com/docs/ref-arch/d2e34e>
- SAP API Policy (PDF) — <https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf>
- Turn SAP APIs into MCP tools with SAP Integration Suite (community blog) — <https://community.sap.com/t5/integration-blog-posts/turn-sap-apis-into-mcp-tools-for-ai-agents-using-sap-integration-suite-free/ba-p/14439352>
- Activate the Integration Cell — <https://help.sap.com/docs/integration-suite/isuite-integrations-and-apis/activate-integration-cell?version=CLOUD>

**This series**
- Video 1 — MCP Gateway on SAP Integration Suite — [`01-integration-suite.md`](./01-integration-suite.md)
- Video 2 — MCP Gateway with Microsoft Entra ID — [`02-entra-id.md`](./02-entra-id.md)
- Video 3 — MCP Gateway with SAP IAS (federated to Entra ID) — [`03-sap-ias.md`](./03-sap-ias.md) — the **direct predecessor** (Phase 1) to this guide

---

## FAQ

<details>
<summary>Do I have to change anything on the Copilot Studio / Entra ID / IAS side?</summary>

No. The entire front end is **unchanged** from the previous video. Users still sign in through **Entra ID federated into IAS**, and the MCP Gateway still validates the **IAS-issued** token and reads `mail`. Video 4 only changes the **backend target and trust**.
</details>

<details>
<summary>Why not just keep Basic Authentication?</summary>

Basic Auth runs **every** call as one shared technical user, so you lose the real user's identity, authorizations, and audit trail in the backend. Principal propagation makes the OData call execute as the **actual person**, so SAP authorizations and logging apply exactly as if they logged in themselves.
</details>

<details>
<summary>Is a 401 a permissions problem?</summary>

No — **401** is an **authentication** failure (the backend couldn't establish *who* you are). A permissions problem would be **403**. If both a low-privilege and a high-privilege user get the **same 401**, it's systemic auth (here: `login/certificate_mapping_rulebased` + restart), not authorizations.
</details>

<details>
<summary>When do the certificates expire?</summary>

The **per-user** certificates are **short-lived** (minted per request by the Cloud Connector). The **CA** and **System Certificate** are long-lived — note their expiry when you create them and renew before they lapse; an expired System Certificate breaks mutual TLS with the same *"not mutually authenticated"* symptom.
</details>
