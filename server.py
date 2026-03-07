import os, json, httpx
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

CLIENT_ID=os.getenv("ZOHO_CLIENT_ID","1000.KNZF8MGNSLXKAHTVVAJEWGHULJUAFC")
CLIENT_SECRET=os.getenv("ZOHO_CLIENT_SECRET","44cbd99a7162c923b33b5cf0365e53c4ab5862d160")
REFRESH_TOKEN=os.getenv("ZOHO_REFRESH_TOKEN","1000.db34a50cdd2603c0fa0438ab9e77f25a.a300ece5a9c25ab764db4268680d51fe")
ORG_ID=os.getenv("ZOHO_ORG_ID","")
DC=os.getenv("ZOHO_DC","com")
BASE=f"https://accounts.zoho.{DC}"
CRM=f"https://www.zohoapis.{DC}/crm/v3"
BOOKS=f"https://www.zohoapis.{DC}/books/v3"
INV=f"https://www.zohoapis.{DC}/inventory/v1"
MAIL=f"https://mail.zoho.{DC}/api"
_tok=None

async def get_token():
    global _tok
    if _tok: return _tok
    async with httpx.AsyncClient() as c:
        r=await c.post(f"{BASE}/oauth/v2/token",data={"refresh_token":REFRESH_TOKEN,"client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"grant_type":"refresh_token"})
        _tok=r.json().get("access_token")
        return _tok

async def zget(url,params=None):
    global _tok
    t=await get_token()
    async with httpx.AsyncClient() as c:
        r=await c.get(url,headers={"Authorization":f"Zoho-oauthtoken {t}"},params=params,timeout=30)
        if r.status_code==401:
            _tok=None;t=await get_token()
            r=await c.get(url,headers={"Authorization":f"Zoho-oauthtoken {t}"},params=params,timeout=30)
        return r.json()

async def zpost(url,body):
    t=await get_token()
    async with httpx.AsyncClient() as c:
        r=await c.post(url,headers={"Authorization":f"Zoho-oauthtoken {t}"},json=body,timeout=30)
        return r.json()

mcp=Server("zoho-mcp")

@mcp.list_tools()
async def list_tools():
    return[
        Tool(name="zoho_crm_list",description="List CRM records (Contacts/Leads/Accounts/Deals)",inputSchema={"type":"object","properties":{"module":{"type":"string","default":"Contacts"},"per_page":{"type":"integer","default":20}}}),
        Tool(name="zoho_crm_search",description="Search CRM records",inputSchema={"type":"object","properties":{"module":{"type":"string","default":"Contacts"},"criteria":{"type":"string"}},"required":["criteria"]}),
        Tool(name="zoho_crm_create",description="Create CRM record",inputSchema={"type":"object","properties":{"module":{"type":"string"},"data":{"type":"object"}},"required":["module","data"]}),
        Tool(name="zoho_books_invoices",description="List Zoho Books invoices",inputSchema={"type":"object","properties":{"status":{"type":"string"},"per_page":{"type":"integer","default":20}}}),
        Tool(name="zoho_books_contacts",description="List Books contacts",inputSchema={"type":"object","properties":{"per_page":{"type":"integer","default":20}}}),
        Tool(name="zoho_inventory_items",description="List inventory items",inputSchema={"type":"object","properties":{"per_page":{"type":"integer","default":20}}}),
        Tool(name="zoho_inventory_orders",description="List sales orders",inputSchema={"type":"object","properties":{"per_page":{"type":"integer","default":20}}}),
        Tool(name="zoho_mail_accounts",description="List Zoho Mail accounts",inputSchema={"type":"object","properties":{}}),
        Tool(name="zoho_mail_messages",description="List emails from inbox",inputSchema={"type":"object","properties":{"account_id":{"type":"string"},"count":{"type":"integer","default":20}},"required":["account_id"]}),
    ]

@mcp.call_tool()
async def call_tool(name,arguments):
    try:
        r=await dispatch(name,arguments)
        return[TextContent(type="text",text=json.dumps(r,ensure_ascii=False,indent=2))]
    except Exception as e:
        return[TextContent(type="text",text=f"Error: {e}")]

async def dispatch(name,a):
    org=ORG_ID
    if name=="zoho_crm_list":return await zget(f"{CRM}/{a.get('module','Contacts')}",{"per_page":a.get("per_page",20)})
    elif name=="zoho_crm_search":return await zget(f"{CRM}/{a.get('module','Contacts')}/search",{"criteria":a["criteria"]})
    elif name=="zoho_crm_create":return await zpost(f"{CRM}/{a['module']}",{"data":[a["data"]]})
    elif name=="zoho_books_invoices":
        p={"organization_id":org,"per_page":a.get("per_page",20)}
        if "status" in a:p["status"]=a["status"]
        return await zget(f"{BOOKS}/invoices",p)
    elif name=="zoho_books_contacts":return await zget(f"{BOOKS}/contacts",{"organization_id":org,"per_page":a.get("per_page",20)})
    elif name=="zoho_inventory_items":return await zget(f"{INV}/items",{"organization_id":org,"per_page":a.get("per_page",20)})
    elif name=="zoho_inventory_orders":return await zget(f"{INV}/salesorders",{"organization_id":org,"per_page":a.get("per_page",20)})
    elif name=="zoho_mail_accounts":return await zget(f"{MAIL}/accounts")
    elif name=="zoho_mail_messages":return await zget(f"{MAIL}/accounts/{a['account_id']}/messages/view",{"limit":a.get("count",20)})
    return{"error":f"Unknown: {name}"}

sse=SseServerTransport("/messages/")

async def handle_sse(request:Request):
    async with sse.connect_sse(request.scope,request.receive,request._send) as streams:
        await mcp.run(streams[0],streams[1],mcp.create_initialization_options())

async def health(request:Request):
    return JSONResponse({"status":"ok","service":"Zoho MCP"})

happ=Starlette(routes=[Route("/health",health),Route("/sse",handle_sse),Route("/exchange",exchange),Mount("/messages/",app=sse.handle_post_message)])


async def exchange(request:Request):
        code=request.query_params.get("code","")
        if not code:return JSONResponse({"error":"no code"})
                async with httpx.AsyncClient() as c:
                            r=await c.post(f"{BASE}/oauth/v2/token",data={"code":code,"client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"redirect_uri":"https://zohoapis.com","grant_type":"authorization_code"})
                            return JSONResponse(r.json())
if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=int(os.getenv("PORT",8000)))
