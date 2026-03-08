import os, json, httpx
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

CLIENT_ID     = os.getenv('ZOHO_CLIENT_ID', '')
CLIENT_SECRET = os.getenv('ZOHO_CLIENT_SECRET', '')
REFRESH_TOKEN = os.getenv('ZOHO_REFRESH_TOKEN', '')
ORG_ID        = os.getenv('ZOHO_ORG_ID', '')
DC            = os.getenv('ZOHO_DC', 'com')

BASE  = f'https://accounts.zoho.{DC}'
CRM   = f'https://www.zohoapis.{DC}/crm/v3'
BOOKS = f'https://www.zohoapis.{DC}/books/v3'
INV   = f'https://www.zohoapis.{DC}/inventory/v1'
MAIL  = f'https://mail.zoho.{DC}/api'

_tok = None

async def get_token():
    global _tok
    if _tok:
        return _tok
    async with httpx.AsyncClient() as c:
        r = await c.post(f'{BASE}/oauth/v2/token', data={
            'refresh_token': REFRESH_TOKEN,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token'
        })
        _tok = r.json().get('access_token')
        return _tok

async def zget(url, params=None):
    global _tok
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.get(url,
            headers={'Authorization': f'Zoho-oauthtoken {t}'},
            params=params, timeout=30)
        if r.status_code == 401:
            _tok = None
            t = await get_token()
            r = await c.get(url,
                headers={'Authorization': f'Zoho-oauthtoken {t}'},
                params=params, timeout=30)
        return r.json()

async def zpost(url, body):
    t = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.post(url,
            headers={'Authorization': f'Zoho-oauthtoken {t}'},
            json=body, timeout=30)
        return r.json()

mcp = Server('zoho-mcp')

@mcp.list_tools()
async def list_tools():
    return [
        Tool(name='zoho_crm_list', description='List CRM records', inputSchema={
            'type': 'object',
            'properties': {
                'module': {'type': 'string', 'description': 'CRM module: Contacts, Leads, Accounts, Deals'},
                'per_page': {'type': 'integer', 'default': 10}
            },
            'required': ['module']
        }),
        Tool(name='zoho_crm_search', description='Search CRM records', inputSchema={
            'type': 'object',
            'properties': {
                'module': {'type': 'string'},
                'criteria': {'type': 'string', 'description': 'Search criteria'}
            },
            'required': ['module', 'criteria']
        }),
        Tool(name='zoho_crm_create', description='Create a new CRM record', inputSchema={
            'type': 'object',
            'properties': {
                'module': {'type': 'string'},
                'data': {'type': 'object', 'description': 'Record fields as key-value pairs'}
            },
            'required': ['module', 'data']
        }),
        Tool(name='zoho_books_invoices', description='List invoices from Zoho Books', inputSchema={
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'description': 'Filter by status: draft, sent, overdue, paid'}
            }
        }),
        Tool(name='zoho_books_contacts', description='List contacts from Zoho Books', inputSchema={
            'type': 'object',
            'properties': {
                'search': {'type': 'string', 'description': 'Search term'}
            }
        }),
        Tool(name='zoho_inventory_items', description='List items from Zoho Inventory', inputSchema={
            'type': 'object',
            'properties': {}
        }),
        Tool(name='zoho_inventory_orders', description='List sales orders from Zoho Inventory', inputSchema={
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'description': 'Filter by status'}
            }
        }),
        Tool(name='zoho_mail_accounts', description='List Zoho Mail accounts', inputSchema={
            'type': 'object',
            'properties': {}
        }),
        Tool(name='zoho_mail_messages', description='Read incoming messages from Zoho Mail', inputSchema={
            'type': 'object',
            'properties': {
                'account_id': {'type': 'string', 'description': 'Mail account ID'},
                'limit': {'type': 'integer', 'default': 10}
            },
            'required': ['account_id']
        }),
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == 'zoho_crm_list':
            module = arguments.get('module', 'Contacts')
            per_page = arguments.get('per_page', 10)
            data = await zget(f'{CRM}/{module}', params={'per_page': per_page})
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_crm_search':
            module = arguments['module']
            criteria = arguments['criteria']
            data = await zget(f'{CRM}/{module}/search', params={'criteria': criteria})
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_crm_create':
            module = arguments['module']
            body = {'data': [arguments['data']]}
            data = await zpost(f'{CRM}/{module}', body)
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_books_invoices':
            params = {}
            if 'status' in arguments:
                params['status'] = arguments['status']
            if ORG_ID:
                params['organization_id'] = ORG_ID
            data = await zget(f'{BOOKS}/invoices', params=params)
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_books_contacts':
            params = {}
            if 'search' in arguments:
                params['contact_name_contains'] = arguments['search']
            if ORG_ID:
                params['organization_id'] = ORG_ID
            data = await zget(f'{BOOKS}/contacts', params=params)
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_inventory_items':
            params = {}
            if ORG_ID:
                params['organization_id'] = ORG_ID
            data = await zget(f'{INV}/items', params=params)
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_inventory_orders':
            params = {}
            if 'status' in arguments:
                params['status'] = arguments['status']
            if ORG_ID:
                params['organization_id'] = ORG_ID
            data = await zget(f'{INV}/salesorders', params=params)
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_mail_accounts':
            data = await zget(f'{MAIL}/accounts')
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif name == 'zoho_mail_messages':
            account_id = arguments['account_id']
            limit = arguments.get('limit', 10)
            data = await zget(f'{MAIL}/accounts/{account_id}/messages/view', params={'limit': limit})
            return [TextContent(type='text', text=json.dumps(data, ensure_ascii=False, indent=2))]

        else:
            return [TextContent(type='text', text=f'Unknown tool: {name}')]

    except Exception as e:
        return [TextContent(type='text', text=f'Error: {str(e)}')]

async def health(request: Request):
    return JSONResponse({'status': 'ok', 'service': 'Zoho MCP'})

sse = SseServerTransport('/messages/')

async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())

app = Starlette(routes=[
    Route('/health', health),
    Route('/sse', handle_sse),
    Mount('/messages/', app=sse.handle_post_message)
])

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
