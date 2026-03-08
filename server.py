import os, json, httpx
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

_tok = None

async def get_token():
    global _tok
    if _tok:
        return _tok
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/oauth/v2/token", data={
            "refresh_token": REFRESH_TOKEN,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "refresh_token",
        })
        _tok = r.json().get("access_token")
        return _tok

async def zget(url, params=None):
    global _tok
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, params=params, timeout=30)
        if r.status_code == 401:
            _tok = None
            t = await get_token()
            r = await c.get(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, params=params, timeout=30)
        return r.json()

async def zpost(url, body):
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.post(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, json=body, timeout=30)
        return r.json()

mcp = Server("zoho-mcp")

@mcp.list_tools()
async def list_tools():
    return [
        Tool(name="zoho_crm_list", description="List CRM records", inputSchema={"type":"object","properties":{"module":{"type":"string"},"per_page":{"type":"integer","default":10}},"required":["module"]}),
        Tool(name="zoho_crm_search", description="Search CRM records", inputSchema={"type":"object","properties":{"module":{"type":"string"},"criteria":{"type":"string"}},"required":["module","criteria"]}),
        Tool(name="zoho_crm_create", description="Create a new CRM record", inputSchema={"type":"object","properties":{"module":{"type":"string"},"data":{"type":"object"}},"required":["module","data"]}),
        Tool(name="zoho_books_invoices", description="List invoices from Zoho Books", inputSchema={"type":"object","properties":{"status":{"type":"string"}}}),
        Tool(name="zoho_books_contacts", description="List contacts from Zoho Books", inputSchema={"type":"object","properties":{"search":{"type":"string"}}}),
        Tool(name="zoho_inventory_items", description="List items from Zoho Inventory", inputSchema={"type":"object","properties":{}}),
        Tool(name="zoho_inventory_orders", description="List sales orders from Zoho Inventory", inputSchema={"type":"object","properties":{"status":{"type":"string"}}}),
        Tool(name="zoho_mail_accounts", description="List Zoho Mail accounts", inputSchema={"type":"object","properties":{}}),
        Tool(name="zoho_mail_messages", description="Read messages from Zoho Mail", inputSchema={"type":"object","properties":{"account_id":{"type":"string"},"limit":{"type":"integer","default":10}},"required":["account_id"]}),
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "zoho_crm_list":
            data = await zget(f"{CRM}/{arguments.get('module','Contacts')}", params={"per_page": arguments.get("per_page", 10)})
        elif name == "zoho_crm_search":
            data = await zget(f"{CRM}/{arguments['module']}/search", params={"criteria": arguments["criteria"]})
        elif name == "zoho_crm_create":
            data = await zpost(f"{CRM}/{arguments['module']}", {"data": [arguments["data"]]})
        elif name == "zoho_books_invoices":
            params = {"organization_id": ORG_ID} if ORG_ID else {}
            if "status" in arguments: params["status"] = arguments["status"]
            data = await zget(f"{BOOKS}/invoices", params=params)
        elif name == "zoho_books_contacts":
            params = {"organization_id": ORG_ID} if ORG_ID else {}
            if "search" in arguments: params["search_text"] = arguments["search"]
            data = await zget(f"{BOOKS}/contacts", params=params)
        elif name == "zoho_inventory_items":
            data = await zget(f"{INV}/items", params={"organization_id": ORG_ID} if ORG_ID else {})
        elif name == "zoho_inventory_orders":
            params = {"organization_id": ORG_ID} if ORG_ID else {}
            if "status" in arguments: params["status"] = arguments["status"]
            data = await zget(f"{INV}/salesorders", params=params)
        elif name == "zoho_mail_accounts":
            data = await zget(f"{MAIL}/accounts")
        elif name == "zoho_mail_messages":
            data = await zget(f"{MAIL}/accounts/{arguments['account_id']}/messages/view", params={"limit": arguments.get("limit", 10)})
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
    return JSONResponse({"status": "ok", "service": "Zoho MCP"})

app = Starlette(routes=[
    Route("/health", health),
    Route("/sse",    handle_sse),
    Mount("/messages/", app=sse.handle_post_message),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
