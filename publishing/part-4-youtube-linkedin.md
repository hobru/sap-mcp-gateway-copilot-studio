# Publishing drafts — Part 4 (On-prem principal propagation)

Draft **LinkedIn post** and **YouTube description** for Video 4 of the series. Video 4 keeps
the Part 3 front-end identity (Microsoft Entra ID federated into SAP IAS) and changes the
**backend** to your own on-prem SAP via the SAP Cloud Connector — first a Basic-Auth foil,
then end-to-end **X.509 principal propagation** so each OData call runs as the real ABAP user.

> Video 4: `https://youtu.be/x64gVHRdVMQ` (publishes Monday — link is live once the video goes public).
> Previous parts: Part 1 `https://youtu.be/1m12OVONavA` · Part 2 `https://youtu.be/jE-qlg2vZ6I` · Part 3 `https://youtu.be/7Y4TH2DWIoo`.

---

## LinkedIn post

🔗 Part 4: The identity finally reaches the **backend** — the SAP OData call now runs as the **real end user**, end to end.

In the last three videos, Microsoft Copilot Studio talked to SAP Integration Suite's **MCP Gateway** and the *gateway* learned who the user was — first a shared technical account, then Microsoft Entra ID, then a token trusted by SAP through **SAP Cloud Identity Services (IAS)**. But the actual backend call still ran as one technical user.

This time we close the loop. 👤➡️🟦

The same IAS-trusted token is now forwarded through the **SAP Cloud Connector**, which mints a **short-lived X.509 certificate per request** and logs the user on to an **on-premise SAP system** — real **principal propagation**. I also swapped the demo backend from the public API to my own SAP `API_BUSINESS_PARTNER` service.

What's in the video:
✅ Pointing the MCP server at an **on-premise Destination** instead of a public API — same policy, new backend
✅ Connecting the **SAP Cloud Connector** from scratch: subaccount, HTTPS system, virtual host, access-control paths
✅ A **60-second Basic-Auth foil** first — proving the Cloud Connector path before adding certificates
✅ The full **principal-propagation** setup: CA + System certificate, STRUST import, CERTRULE email mapping
✅ The three ABAP profile parameters that actually cost me the most time — including `login/certificate_mapping_rulebased = 1` and `icm/trusted_reverse_proxy` (with a full system restart)
✅ Flipping the Destination from Basic Auth to **Principal Propagation** and proving two different users land as two different SAP users — in the Cloud Connector Monitor **and** the SAP traces

The result: no shared service user, no lost identity. SAP **authorizations and audit logging** apply to the actual person behind the agent. 🔒

The MCP Gateway remains one of the two integration architectures **endorsed by SAP** in the SAP API Policy — this is the clean, standards-based way to bring agentic AI to SAP.

Most of the effort here is **pure SAP configuration** (Cloud Connector + ABAP trust), so I documented every step, every dead end, and every fix in the guide.

▶️ Watch it here: https://youtu.be/x64gVHRdVMQ
📄 Full step-by-step guide, troubleshooting notes + a VS Code REST Client script in the description.

#SAP #MicrosoftCopilot #CopilotStudio #EntraID #SAPIAS #MCP #IntegrationSuite #PrincipalPropagation #CloudConnector #AgenticAI #CleanCore #SAPBTP

---

## YouTube description

Connect Microsoft Copilot Studio to your own on-premise SAP system with REAL end-to-end user identity — using the Model Context Protocol (MCP) Gateway on SAP Integration Suite, SAP Cloud Identity Services (IAS), the SAP Cloud Connector, and X.509 principal propagation.

This is Part 4. In Parts 1–3 the MCP Gateway learned the user's identity (technical account → Microsoft Entra ID → a token trusted by SAP via IAS), but the backend OData call still ran as a single technical user. Here we forward that IAS-trusted token through the SAP Cloud Connector, which mints a short-lived X.509 certificate per request and logs the actual user on to an on-premise SAP system — real principal propagation. The demo backend also moves from the public API to SAP API_BUSINESS_PARTNER.

You'll see the full flow: repointing the MCP server at an on-premise Destination, connecting the Cloud Connector from scratch (subaccount, HTTPS system, virtual host, access-control paths, back-end trust store), a quick Basic-Auth foil to prove the path, then the complete principal-propagation setup — CA + System certificate, STRUST import, the three ABAP profile parameters (including login/certificate_mapping_rulebased and icm/trusted_reverse_proxy) with a system restart, CERTRULE email mapping, and finally flipping the Destination to Principal Propagation. We prove two different users land as two different SAP users in the Cloud Connector Monitor and the SAP traces.

The MCP Gateway is one of two architectures endorsed by SAP in the SAP API Policy.

▶️ Part 1 — MCP Gateway on SAP Integration Suite: https://youtu.be/1m12OVONavA
▶️ Part 2 — MCP Gateway with Microsoft Entra ID: https://youtu.be/jE-qlg2vZ6I
▶️ Part 3 — MCP Gateway with SAP Identity Services (IAS): https://youtu.be/7Y4TH2DWIoo

⏱️ Chapters
00:00 Recap of Part 3 and what this video adds
00:34 How this video is structured: quick changes, then the deep Cloud Connector + PP setup
01:17 End-user demo in Copilot Studio — full single sign-on, also in Teams
02:59 Same MCP policy, new backend: from the public API to an on-premise Destination
03:58 The Business Partner OData API and its OpenAPI specification
04:37 Anatomy of the on-premise Destination and the Cloud Connector
06:35 The trust chain: IAS/Entra token → Cloud Connector → short-lived X.509 → STRUST + email mapping
08:02 Building it: from the IAS-only MCP server toward the Destination
09:09 Connecting the SAP Cloud Connector to the BTP subaccount
10:23 Adding the on-premise ABAP system over HTTPS
11:42 "Not reachable" — importing the backend certificate into the Cloud Connector back-end trust store
12:45 Exposing the access-control paths (/sap/opu/odata and /sap/bc)
13:31 Creating the BTP Destination with Basic Authentication (+ the Integration Cell property)
14:44 Generating the MCP server from the Business Partner OpenAPI spec
15:38 Adjusting the MCP policy (reusing the IAS/Entra settings) and deploying
16:41 Basic-Auth foil proven in Copilot Studio — the Cloud Connector path works
17:35 Switching to principal propagation: creating the CA + System certificates in the Cloud Connector
18:43 Importing both certificates into SAP (STRUST, SSL server Standard)
19:37 The ABAP profile parameters (rule-based mapping, trusted reverse proxy) and a full system restart
20:34 Rule-based certificate mapping (CERTRULE) using the email attribute
21:06 Testing the mapping with a Cloud Connector sample certificate and mapping the SAP user
22:24 Flipping the Destination from Basic Auth to Principal Propagation
23:13 End-to-end test in Copilot Studio (10 business partners) with principal propagation
23:57 Verifying the real end-user identity in the Cloud Connector Monitor
24:29 Confirming the call runs as the mapped user in the SAP system traces

🔗 Resources
SAP Reference Architecture (MCP Gateway): https://architecture.learning.sap.com/docs/ref-arch/d2e34e
SAP API Policy (PDF): https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf
Turn SAP APIs into MCP tools with SAP Integration Suite (community blog): https://community.sap.com/t5/integration-blog-posts/turn-sap-apis-into-mcp-tools-for-ai-agents-using-sap-integration-suite-free/ba-p/14439352
Configure Principal Propagation in the Cloud Connector: https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/configure-cloud-connector-for-principal-propagation
Set up trust for principal propagation (CA + System Certificate): https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/set-up-trust-for-principal-propagation
Trusted reverse proxy (icm/trusted_reverse_proxy) — SAP Note 3335949: https://me.sap.com/notes/3335949
Activate the Integration Cell: https://help.sap.com/docs/integration-suite/isuite-integrations-and-apis/activate-integration-cell?version=CLOUD

#SAP #MicrosoftCopilot #CopilotStudio #EntraID #SAPIAS #MCP #IntegrationSuite #PrincipalPropagation #CloudConnector #AgenticAI
