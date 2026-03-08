import os, json, asyncio, time, httpx
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

CLIENT_ID     = os.getenv("ZOHO_CLIENT_ID",     "1000.MJ0WMRO1FMQVLK0AZYVKF7PNFN175T")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "791b2e386192c8d738b5e931aa0d90e340ef73a3da")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "1000.fd4adbe0d23f4dc68d98462211f9c183.3bb538284a6044fb19fae39fb2d51593")
ORG_ID        = os.getenv("ZOHO_ORG_ID", "")
DC            = os.getenv("ZOHO_DC", "com")

BASE  = f"https://accounts.zoho.{DC}"
CRM   = f"https://www.zohoapis.{DC}/crm/v3"
BOOKS = f"https://www.zohoapis.{DC}/books/v3"
INV   = f"https://www.zohoapis.{DC}/inventory/v1"
MAIL  = f"https://mail.zoho.{DC}/api"

TOKEN_TTL = 50 * 60

_tok      = None
_tok_time = 0.0


async def _fetch_token() -> str:
    global _tok, _tok_time
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/oauth/v2/token", data={
            "refresh_token": REFRESH_TOKEN,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "refresh_token",
        })
        token = r.json().get("access_token")
        if token:
            _tok      = token
            _tok_time = time.time()
            print(f"[token] refreshed at {time.strftime('%H:%M:%S')}", flush=True)
        return _tok


async def get_token() -> str:
    if _tok and (time.time() - _tok_time) < TOKEN_TTL:
        return _tok
    return await _fetch_token()


async def _auto_refresh():
    await _fetch_token()
    while True:
        await asyncio.sleep(TOKEN_TTL)
        try:
            await _fetch_token()
        except Exception as e:
            print(f"[token] auto-refresh failed: {e}", flush=True)


async def zget(url, params=None):
    global _tok
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, params=params, timeout=30)
        if r.status_code == 401:
            _tok = None
            t = await _fetch_token()
            r = await c.get(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, params=params, timeout=30)
        return r.json()


async def zpost(url, body):
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.post(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, json=body, timeout=30)
        return r.json()


async def zput(url, body):
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.put(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, json=body, timeout=30)
        return r.json()


async def zdelete(url):
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.delete(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, timeout=30)
        return r.json()


mcp = Server("zoho-mcp")


@mcp.list_tools()
async def list_tools():
    return [
        # ── CRM ──────────────────────────────────────────────────
        Tool(name="zoho_crm_list", description="List CRM records (Contacts/Leads/Accounts/Deals)", inputSchema={
            "type": "object",
            "properties": {
                "module":   {"type": "string", "description": "Contacts, Leads, Accounts, Deals"},
                "per_page": {"type": "integer", "default": 10},
            },
            "required": ["module"],
        }),
        Tool(name="zoho_crm_search", description="Search CRM records by criteria", inputSchema={
            "type": "object",
            "properties": {
                "module":   {"type": "string"},
                "criteria": {"type": "string", "description": "e.g. (Email:equals:test@example.com)"},
            },
            "required": ["module", "criteria"],
        }),
        Tool(name="zoho_crm_create", description="Create a new CRM record", inputSchema={
            "type": "object",
            "properties": {
                "module": {"type": "string"},
                "data":   {"type": "object"},
            },
            "required": ["module", "data"],
        }),
        Tool(name="zoho_crm_update", description="Update an existing CRM record by ID", inputSchema={
            "type": "object",
            "properties": {
                "module":    {"type": "string"},
                "record_id": {"type": "string"},
                "data":      {"type": "object"},
            },
            "required": ["module", "record_id", "data"],
        }),
        Tool(name="zoho_crm_delete", description="Delete a CRM record by ID", inputSchema={
            "type": "object",
            "properties": {
                "module":    {"type": "string"},
                "record_id": {"type": "string"},
            },
            "required": ["module", "record_id"],
        }),
        # ── Books ─────────────────────────────────────────────────
        Tool(name="zoho_books_invoices", description="List invoices from Zoho Books", inputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "draft, sent, overdue, paid, void"},
            },
        }),
        Tool(name="zoho_books_create_invoice", description="Create a new invoice in Zoho Books", inputSchema={
            "type": "object",
            "properties": {
                "customer_id":   {"type": "string"},
                "line_items":    {"type": "array",  "description": "List of {item_id, quantity, rate}"},
                "invoice_date":  {"type": "string", "description": "YYYY-MM-DD"},
                "due_date":      {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["customer_id", "line_items"],
        }),
        Tool(name="zoho_books_contacts", description="List contacts from Zoho Books", inputSchema={
            "type": "object",
            "properties": {
                "search": {"type": "string"},
            },
        }),
        # ── Inventory ─────────────────────────────────────────────
        Tool(name="zoho_inventory_items", description="List items from Zoho Inventory", inputSchema={
            "type": "object", "properties": {},
        }),
        Tool(name="zoho_inventory_orders", description="List sales orders from Zoho Inventory", inputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "draft, confirmed, shipped, delivered"},
            },
        }),
        Tool(name="zoho_inventory_create_item", description="Add a new item/product to Zoho Inventory", inputSchema={
            "type": "object",
            "properties": {
                "name":         {"type": "string"},
                "rate":         {"type": "number"},
                "description":  {"type": "string"},
                "sku":          {"type": "string"},
                "unit":         {"type": "string"},
            },
            "required": ["name", "rate"],
        }),
        # ── Mail ──────────────────────────────────────────────────
        Tool(name="zoho_mail_accounts", description="List Zoho Mail accounts", inputSchema={
            "type": "object", "properties": {},
        }),
        Tool(name="zoho_mail_messages", description="Read recent messages from Zoho Mail", inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "limit":      {"type": "integer", "default": 10},
            },
            "required": ["account_id"],
        }),
        Tool(name="zoho_mail_send", description="Send an email via Zoho Mail", inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "to":         {"type": "string", "description": "Recipient email"},
                "subject":    {"type": "string"},
                "body":       {"type": "string"},
            },
            "required": ["account_id", "to", "subject", "body"],
        }),
    ]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        org = {"organization_id": ORG_ID} if ORG_ID else {}

        # ── CRM ──────────────────────────────────────────────────
        if name == "zoho_crm_list":
            data = await zget(
                f"{CRM}/{arguments.get('module', 'Contacts')}",
                params={"per_page": arguments.get("per_page", 10), "fields": "Full_Name,Email,Phone,Account_Name"},
            )
        elif name == "zoho_crm_search":
            data = await zget(
                f"{CRM}/{arguments['module']}/search",
                params={"criteria": arguments["criteria"]},
            )
        elif name == "zoho_crm_create":
            data = await zpost(f"{CRM}/{arguments['module']}", {"data": [arguments["data"]]})

        elif name == "zoho_crm_update":
            data = await zput(
                f"{CRM}/{arguments['module']}/{arguments['record_id']}",
                {"data": [arguments["data"]]},
            )
        elif name == "zoho_crm_delete":
            data = await zdelete(f"{CRM}/{arguments['module']}/{arguments['record_id']}")

        # ── Books ─────────────────────────────────────────────────
        elif name == "zoho_books_invoices":
            params = {**org}
            if "status" in arguments:
                params["status"] = arguments["status"]
            data = await zget(f"{BOOKS}/invoices", params=params)

        elif name == "zoho_books_create_invoice":
            body = {
                "customer_id": arguments["customer_id"],
                "line_items":  arguments["line_items"],
            }
            if "invoice_date" in arguments: body["invoice_date"] = arguments["invoice_date"]
            if "due_date"     in arguments: body["due_date"]     = arguments["due_date"]
            params = org if org else {}
            data = await zpost(f"{BOOKS}/invoices" + (f"?organization_id={ORG_ID}" if ORG_ID else ""), body)

        elif name == "zoho_books_contacts":
            params = {**org}
            if "search" in arguments:
                params["search_text"] = arguments["search"]
            data = await zget(f"{BOOKS}/contacts", params=params)

        # ── Inventory ─────────────────────────────────────────────
        elif name == "zoho_inventory_items":
            data = await zget(f"{INV}/items", params=org)

        elif name == "zoho_inventory_orders":
            params = {**org}
            if "status" in arguments:
                params["status"] = arguments["status"]
            data = await zget(f"{INV}/salesorders", params=params)

        elif name == "zoho_inventory_create_item":
            body = {"name": arguments["name"], "rate": arguments["rate"]}
            for k in ("description", "sku", "unit"):
                if k in arguments:
                    body[k] = arguments[k]
            url = f"{INV}/items" + (f"?organization_id={ORG_ID}" if ORG_ID else "")
            data = await zpost(url, body)

        # ── Mail ──────────────────────────────────────────────────
        elif name == "zoho_mail_accounts":
            data = await zget(f"{MAIL}/accounts")

        elif name == "zoho_mail_messages":
            data = await zget(
                f"{MAIL}/accounts/{arguments['account_id']}/messages/view",
                params={"limit": arguments.get("limit", 10)},
            )
        elif name == "zoho_mail_send":
            body = {
                "fromAddress": "",
                "toAddress":   arguments["to"],
                "subject":     arguments["subject"],
                "content":     arguments["body"],
                "mailFormat":  "plaintext",
            }
            data = await zpost(f"{MAIL}/accounts/{arguments['account_id']}/messages", body)

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


sse = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())


async def health(request: Request):
    age = int(time.time() - _tok_time) if _tok_time else -1
    return JSONResponse({"status": "ok", "service": "Zoho MCP", "token_age_sec": age})


async def on_startup():
    asyncio.create_task(_auto_refresh())


app = Starlette(
    routes=[
        Route("/health", health),
        Route("/sse",    handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
    on_startup=[on_startup],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
