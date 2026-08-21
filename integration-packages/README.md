# Importable Integration Suite packages

These are ready-made **SAP Integration Suite content-package exports** for the MCP Gateway, provided as working examples for the **Sales**, **Finance**, and **Procurement** agent scenarios. Each `.zip` is a content package you can import directly into your own Integration Suite tenant.

## What's here

| Package | Flows | Endpoints covered |
|---|---|---|
| [`BPS-Agents-Sales.zip`](./BPS-Agents-Sales.zip) | 7 | Business Partner, Customer Return, Outbound Delivery, Product, Sales Inquiry, Sales Order, Sales Quotation |
| [`BPS-Agents-Finance.zip`](./BPS-Agents-Finance.zip) | 6 | Chart of Accounts, GL Account in Chart of Accounts, GL Account Line Item, Journal Entry Item Basic, Operational Acctg Doc Item Cube, Supplier Invoice |
| [`BPS-Agents-Procurement.zip`](./BPS-Agents-Procurement.zip) | 8 | Info Record, Purchase Contract, Purchase Order, Purchase Requisition, Supplier Quotation (QTN), RFQ, Service Entry Sheet, Supplier Invoice |

Together they map **1:1 to the 21 endpoints** documented in [Part 5](../guides/05-bulk-connector-automation.md) — Sales (7) + Finance (6) + Procurement (8).

## How to import

1. Open **Integration Suite** → **Design** → **Integrations and APIs**.
2. From **(Actions)** choose **Import integration package** and select one of the `.zip` files above.
3. After import, **deploy** the integration flows in the package.

Each deployed flow is **one MCP Gateway endpoint**, fronted by one of the 21 connectors created in Part 5. Importing these packages lets you stand up the MCP Gateway side quickly before you generate and deploy the connectors.

## Note

These exports carry their **source subaccount name** internally and are provided **as-is**. After import, adjust destinations and credentials to match your own tenant.
