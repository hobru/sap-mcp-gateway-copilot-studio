#!/usr/bin/env python3
"""
Generate-Connectors.py — scaffold Power Platform custom-connector definitions
for the 21 SAP MCP Gateway endpoints (Sales 7 / Finance 6 / Procurement 8).

For every endpoint it writes a folder <output>/<CONNECTOR_NAME>/ containing the
trio of files that `pac connector create` expects:

  apiDefinition.swagger.json  OpenAPI 2.0 for the connector's single MCP
                              operation, pointed at
                              https://<integration-host>/<CONNECTOR_NAME>.
  apiProperties.json          SAP IAS OAuth 2.0 block (authorize / token /
                              refresh URLs, scope, client id) — NO client secret.
  settings.json               Power Platform environment + per-connector
                              metadata (intended title, functional area).

The client SECRET is never written here. Deploy-Connectors.ps1 prompts for it
securely at deploy time and passes it straight to `pac connector create`.

All identity values default to safe PLACEHOLDERS (matching guide 05). Override
them with CLI flags or environment variables so nothing tenant-specific is ever
committed:

  python Generate-Connectors.py \
      --integration-host  mcaps-xxxxxxxx-cloud.sap \
      --environment       00000000-0000-0000-0000-000000000000 \
      --client-id         11111111-1111-1111-1111-111111111111 \
      --ias-host          myXXXXXX.accounts.ondemand.com

Env-var equivalents: MCP_INTEGRATION_HOST, MCP_ENVIRONMENT, MCP_CLIENT_ID,
MCP_IAS_HOST.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# --- Safe placeholder defaults (identical to guide 05) -----------------------
DEFAULT_INTEGRATION_HOST = "mcaps-xxxxxxxx-cloud.sap"
DEFAULT_ENVIRONMENT = "00000000-0000-0000-0000-000000000000"
DEFAULT_CLIENT_ID = "11111111-1111-1111-1111-111111111111"
DEFAULT_IAS_HOST = "myXXXXXX.accounts.ondemand.com"
SCOPE = "openid email profile offline_access"

# Power Platform hard-caps a connector title at 30 characters.
MAX_TITLE = 30

# --- The 21 endpoints --------------------------------------------------------
# name    = MCP Gateway endpoint path (also the connector name)
# area    = Sales | Finance | Procurement
# entity  = human label used to build the title "SAP {area} - {entity} - MCP"
# service = the underlying SAP OData service (documentation only)
ENDPOINTS = [
    # ---- Sales (7) ----
    {"name": "MCP_SALES_BUSINESS_PARTNER",            "area": "Sales",       "entity": "Business Partner",   "service": "API_BUSINESS_PARTNER"},
    {"name": "MCP_SALES_CUSTOMER_RETURN_SRV",         "area": "Sales",       "entity": "Customer Return",    "service": "API_CUSTOMER_RETURN_SRV"},
    {"name": "MCP_SALES_OUTBOUND_DELIVERY_SRV",       "area": "Sales",       "entity": "Outbound Delivery",  "service": "API_OUTBOUND_DELIVERY_SRV"},
    {"name": "MCP_SALES_PRODUCT_SRV",                 "area": "Sales",       "entity": "Product",            "service": "API_PRODUCT_SRV"},
    {"name": "MCP_SALES_SALES_INQUIRY_SRV",           "area": "Sales",       "entity": "Sales Inquiry",      "service": "API_SALES_INQUIRY_SRV"},
    {"name": "MCP_SALES_SALES_ORDER_SRV",             "area": "Sales",       "entity": "Sales Order",        "service": "API_SALES_ORDER_SRV"},
    {"name": "MCP_SALES_SALES_QUOTATION_SRV",         "area": "Sales",       "entity": "Sales Quotation",    "service": "API_SALES_QUOTATION_SRV"},
    # ---- Finance (6) ----
    {"name": "MCP_FIN_CHARTOFACCOUNTS_SRV",           "area": "Finance",     "entity": "Chart of Accounts",  "service": "API_CHARTOFACCOUNTS_SRV"},
    {"name": "MCP_FIN_GLACCOUNTINCHARTOFACCOUNTS_SRV","area": "Finance",     "entity": "G/L in CoA",         "service": "API_GLACCOUNTINCHARTOFACCOUNTS_SRV"},
    {"name": "MCP_FIN_GLACCOUNTLINEITEM",             "area": "Finance",     "entity": "G/L Line Item",      "service": "API_GLACCOUNTLINEITEM"},
    {"name": "MCP_FIN_JOURNALENTRYITEMBASIC_SRV",     "area": "Finance",     "entity": "Journal Entry",      "service": "API_JOURNALENTRYITEMBASIC_SRV"},
    {"name": "MCP_FIN_OPLACCTGDOCITEMCUBE_SRV",       "area": "Finance",     "entity": "Acctg Doc Item",     "service": "API_OPLACCTGDOCITEMCUBE_SRV"},
    {"name": "MCP_FIN_SUPPLIERINVOICE_PROCESS_SRV",   "area": "Finance",     "entity": "Supplier Invoice",   "service": "API_SUPPLIERINVOICE_PROCESS_SRV"},
    # ---- Procurement (8) ----
    {"name": "MCP_PROC_INFORECORD_PROCESS_SRV",       "area": "Procurement", "entity": "Info Record",        "service": "API_INFORECORD_PROCESS_SRV"},
    {"name": "MCP_PROC_PURCHASECONTRACT_PROCESS_SRV", "area": "Procurement", "entity": "Purchase Contract",  "service": "API_PURCHASECONTRACT_PROCESS_SRV"},
    {"name": "MCP_PROC_PURCHASEORDER_PROCESS_SRV",    "area": "Procurement", "entity": "Purchase Order",     "service": "API_PURCHASEORDER_PROCESS_SRV"},
    {"name": "MCP_PROC_PURCHASEREQ_PROCESS_SRV",      "area": "Procurement", "entity": "Purchase Req",       "service": "API_PURCHASEREQ_PROCESS_SRV"},
    {"name": "MCP_PROC_QTN_PROCESS_SRV",              "area": "Procurement", "entity": "Supplier Quotation", "service": "API_QTN_PROCESS_SRV"},
    {"name": "MCP_PROC_RFQ_PROCESS_SRV",              "area": "Procurement", "entity": "RFQ",                "service": "API_RFQ_PROCESS_SRV"},
    {"name": "MCP_PROC_SERVICE_ENTRY_SHEET_SRV",      "area": "Procurement", "entity": "Service Entry Sheet","service": "API_SERVICE_ENTRY_SHEET_SRV"},
    {"name": "MCP_PROC_SUPPLIERINVOICE_PROCESS_SRV",  "area": "Procurement", "entity": "Supplier Invoice",   "service": "API_SUPPLIERINVOICE_PROCESS_SRV"},
]


def make_title(area: str, entity: str) -> str:
    """Build 'SAP {area} - {entity} - MCP', capped at the 30-char platform limit."""
    title = f"SAP {area} - {entity} - MCP"
    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE].rstrip(" -")
    return title


def api_definition(ep: dict, host: str, ias_host: str) -> dict:
    title = make_title(ep["area"], ep["entity"])
    authorize = f"https://{ias_host}/oauth2/authorize"
    token = f"https://{ias_host}/oauth2/token"
    return {
        "swagger": "2.0",
        "info": {
            "title": title,
            "description": f"MCP server for SAP {ep['service']} ({ep['area']}).",
            "version": "1.0",
        },
        "host": host,
        "basePath": "/",
        "schemes": ["https"],
        "consumes": [],
        "produces": [],
        "paths": {
            f"/{ep['name']}": {
                "post": {
                    "summary": title,
                    "description": f"MCP server for SAP {ep['service']} ({ep['area']}).",
                    "operationId": "InvokeMCP",
                    "x-ms-agentic-protocol": "mcp-streamable-1.0",
                    "responses": {"200": {"description": "Success"}},
                }
            }
        },
        "definitions": {},
        "parameters": {},
        "responses": {},
        "securityDefinitions": {
            "oauth2-auth": {
                "type": "oauth2",
                "flow": "accessCode",
                "authorizationUrl": authorize,
                "tokenUrl": token,
                "scopes": {"openid": "openid"},
            }
        },
        "security": [{"oauth2-auth": ["openid"]}],
        "tags": [],
    }


def api_properties(client_id: str, ias_host: str) -> dict:
    authorize = f"https://{ias_host}/oauth2/authorize"
    token = f"https://{ias_host}/oauth2/token"
    # NOTE: clientSecret is intentionally absent. Deploy-Connectors.ps1 injects it
    # into a temp copy at runtime; it is never persisted or committed.
    return {
        "properties": {
            "connectionParameters": {
                "token": {
                    "type": "oauthSetting",
                    "oAuthSettings": {
                        "identityProvider": "oauth2",
                        "clientId": client_id,
                        "scopes": ["openid"],
                        "redirectMode": "GlobalPerConnector",
                        "redirectUrl": "https://global.consent.azure-apim.net/redirect",
                        "properties": {
                            "IsFirstParty": "False",
                            "IsOnbehalfofLoginSupported": False,
                        },
                        "customParameters": {
                            "authorizationUrl": {"value": authorize},
                            "tokenUrl": {"value": token},
                            "refreshUrl": {"value": token},
                        },
                    },
                }
            },
            "iconBrandColor": "#007ee5",
            "capabilities": [],
            "policyTemplateInstances": [],
        }
    }


def settings(ep: dict, environment: str) -> dict:
    return {
        "environment": environment,
        "connectorId": "",
        "title": make_title(ep["area"], ep["entity"]),
        "area": ep["area"],
        "service": ep["service"],
    }


def env_default(var: str, fallback: str) -> str:
    return os.environ.get(var, fallback)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaffold the 21 SAP MCP connector definitions.")
    p.add_argument("--integration-host", default=env_default("MCP_INTEGRATION_HOST", DEFAULT_INTEGRATION_HOST),
                   help="Integration Suite runtime host (no scheme).")
    p.add_argument("--environment", default=env_default("MCP_ENVIRONMENT", DEFAULT_ENVIRONMENT),
                   help="Power Platform environment id.")
    p.add_argument("--client-id", default=env_default("MCP_CLIENT_ID", DEFAULT_CLIENT_ID),
                   help="SAP IAS App-2 OAuth client id (not a secret).")
    p.add_argument("--ias-host", default=env_default("MCP_IAS_HOST", DEFAULT_IAS_HOST),
                   help="SAP IAS host, e.g. myXXXXXX.accounts.ondemand.com.")
    p.add_argument("--output", default=str(Path(__file__).resolve().parent / "generated"),
                   help="Output directory (default: ./generated next to this script).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    for ep in ENDPOINTS:
        d = out / ep["name"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "apiDefinition.swagger.json").write_text(
            json.dumps(api_definition(ep, args.integration_host, args.ias_host), indent=2), encoding="utf-8")
        (d / "apiProperties.json").write_text(
            json.dumps(api_properties(args.client_id, args.ias_host), indent=2), encoding="utf-8")
        (d / "settings.json").write_text(
            json.dumps(settings(ep, args.environment), indent=2), encoding="utf-8")

    counts: dict[str, int] = {}
    for ep in ENDPOINTS:
        counts[ep["area"]] = counts.get(ep["area"], 0) + 1
    summary = ", ".join(f"{a} {counts[a]}" for a in ("Sales", "Finance", "Procurement"))
    print(f"Generated {len(ENDPOINTS)} connector definitions ({summary}) into: {out}")
    print(f"Integration host: {args.integration_host}")
    print(f"Environment     : {args.environment}")
    print(f"Client id       : {args.client_id}")
    print(f"IAS host        : {args.ias_host}")
    print(f"Scope           : {SCOPE}")
    print("Client secret   : (not written -- prompted at deploy time)")


if __name__ == "__main__":
    main()
