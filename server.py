import os, json, httpx, base64, re
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

CLIENT_ID     = os.getenv("ZOHO_CLIENT_ID",     "1000.KNZF8MGNSLXKAHTVVAJEWGHULJUAFC")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "44cbd99a7162c923b33b5cf0365e53c4ab5862d160")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "EXPIRED")
ORG_ID        = os.getenv("ZOHO_ORG_ID", "")
DC            = os.getenv("ZOHO_DC", "com")
GH_TOKEN      = os.getenv("GITHUB_TOKEN", "")
GH_OWNER      = "azoooz173"
GH_REPO       = "zoho-mcp-server"
GH_FILE       = "server.py"

BASE  = f"https://accounts.zoho.{DC}"
CRM   = f"https://www.zohoapis.{DC}/crm/v3"
BOOKS = f"https://www.zohoapis.{DC}/books/v3"
INV   = f"https://www.zohoapis.{DC}/inventory/v1"
MAIL  = f"https://mail.zoho.{DC}/api"
_tok = None

async def get_token():
    global _tok
    if _tok: return _tok
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/oauth/v2/token", data={
            "refresh_token": REFRESH_TOKEN, "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET, "grant_type": "refresh_token"})
        _tok = r.json().get("access_token")
        return _tok

async def zget(url, params=None):
    global _tok
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers={"Authorization": f"Zoho-oauthtoken {t}"}, params=params, timeout=30)
        if r.status_code == 401:
            _tok = None; t = await get_token()
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
        Tool(name="zoho_books_invoices", description="List invoices", inputSchema={"type":"object","properties":{"status":{"type":"string"}}}),
        Tool(name="zoho_books_contacts", description="List contacts from Books", inputSchema={"type":"object","properties":{"search":{"type":"string"}}}),
        Tool(name="zoho_inventory_items", description="List inventory items", inputSchema={"type":"object","properties":{}}),
        Tool(name="zoho_inventory_orders", description="List sales orders", inputSchema={"type":"object","properties":{"status":{"type":"string"}}}),
        Tool(name="zoho_mail_accounts", description="List mail accounts", inputSchema={"type":"object","properties":{}}),
        Tool(name="zoho_mail_messages", description="Read mail messages", inputSchema={"type":"object","properties":{"account_id":{"type":"string"},"limit":{"type":"integer","default":10}},"required":["account_id"]}),
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "zoho_crm_list":
            return [TextContent(type="text", text=json.dumps(await zget(f"{CRM}/{arguments.get('module','Contacts')}", params={"per_page": arguments.get("per_page",10)}), ensure_ascii=False, indent=2))]
        elif name == "zoho_crm_search":
            return [TextContent(type="text", text=json.dumps(await zget(f"{CRM}/{arguments['module']}/search", params={"criteria": arguments["criteria"]}), ensure_ascii=False, indent=2))]
        elif name == "zoho_crm_create":
            return [TextContent(type="text", text=json.dumps(await zpost(f"{CRM}/{arguments['module']}", {"data": [arguments["data"]]}), ensure_ascii=False, indent=2))]
        elif name == "zoho_books_invoices":
            p={}; p.update({"status":arguments["status"]} if "status" in arguments else {}); p.update({"organization_id":ORG_ID} if ORG_ID else {})
            return [TextContent(type="text", text=json.dumps(await zget(f"{BOOKS}/invoices", params=p), ensure_ascii=False, indent=2))]
        elif name == "zoho_books_contacts":
            p={}; p.update({"search_text":arguments["search"]} if "search" in arguments else {}); p.update({"organization_id":ORG_ID} if ORG_ID else {})
            return [TextContent(type="text", text=json.dumps(await zget(f"{BOOKS}/contacts", params=p), ensure_ascii=False, indent=2))]
        elif name == "zoho_inventory_items":
            return [TextContent(type="text", text=json.dumps(await zget(f"{INV}/items", params={"organization_id":ORG_ID} if ORG_ID else {}), ensure_ascii=False, indent=2))]
        elif name == "zoho_inventory_orders":
            p={}; p.update({"status":arguments["status"]} if "status" in arguments else {}); p.update({"organization_id":ORG_ID} if ORG_ID else {})
            return [TextContent(type="text", text=json.dumps(await zget(f"{INV}/salesorders", params=p), ensure_ascii=False, indent=2))]
        elif name == "zoho_mail_accounts":
            return [TextContent(type="text", text=json.dumps(await zget(f"{MAIL}/accounts"), ensure_ascii=False, indent=2))]
        elif name == "zoho_mail_messages":
            return [TextContent(type="text", text=json.dumps(await zget(f"{MAIL}/accounts/{arguments['account_id']}/messages/view", params={"limit":arguments.get("limit",10)}), ensure_ascii=False, indent=2))]
        else: return [TextContent(type="text", text=f"Unknown: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]

sse = SseServerTransport("/messages/")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())

async def health(request: Request):
    return JSONResponse({"status": "ok", "service": "Zoho MCP"})

async def exchange_grant(request: Request):
    code = request.query_params.get("code", "")
    if not code: return JSONResponse({"error": "no code"})
    for uri in ["urn:ietf:wg:oauth:2.0:oob", "http://localhost:8765/callback"]:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{BASE}/oauth/v2/token", data={"code":code,"client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"redirect_uri":uri,"grant_type":"authorization_code"})
            result = r.json()
            if "refresh_token" in result:
                await _save_token(result['refresh_token'])
                return JSONResponse({"status":"ok","refresh_token":result["refresh_token"]})
    return JSONResponse({"error":"failed","detail":result})

async def set_refresh(request: Request):
    tok = request.query_params.get("token","")
    if not tok: return JSONResponse({"error":"no token"})
    await _save_token(tok)
    return JSONResponse({"status":"ok","saved":tok[:25]+"..."})

async def _save_token(new_tok: str):
    h = {"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json","Content-Type":"application/json","User-Agent":"zoho-mcp"}
    async with httpx.AsyncClient() as c:
        r = await c.get(f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{GH_FILE}", headers=h)
        fd = r.json()
        content = base64.b64decode(fd["content"].replace("\n","")).decode()
        content = re.sub(r'REFRESH_TOKEN = os\.getenv\("ZOHO_REFRESH_TOKEN",\s*"[^"]*"\)',f'REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "{new_tok}")',content)
        await c.put(f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{GH_FILE}",headers=h,json={"message":"fix: update token","content":base64.b64encode(content.encode()).decode(),"sha":fd["sha"],"branch":"main"})

app = Starlette(routes=[
    Route("/health", health),
    Route("/exchange", exchange_grant),
    Route("/set_refresh", set_refresh),
    Route("/sse", handle_sse),
    Mount("/messages/", app=sse.handle_post_message),
])
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))