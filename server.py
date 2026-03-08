import os, json, httpx
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

CLIENT_ID = os.getenv('ZOHO_CLIENT_ID', '1000.KNZF8MGNSLXKAHTVVAJEWGHULJUAFC')
CLIENT_SECRET = os.getenv('ZOHO_CLIENT_SECRET', '44cbd99a7162c923b33b5cf0365e53c4ab5862d160')
REFRESH_TOKEN = os.getenv('ZOHO_REFRESH_TOKEN', '1000.db34a50cdd2603c0fa0438ab9e77f25a.a300ece5a9c25ab764db4268680d51fe')
ORG_ID = os.getenv('ZOHO_ORG_ID', '')
DC = os.getenv('ZOHO_DC', 'com')

BASE = f'https://accounts.zoho.{DC}'
CRM = f'https://www.zohoapis.{DC}/crm/v3'
BOOKS = f'https://www.zohoapis.{DC}/books/v3'
INV = f'himport os, json, httpx
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

CLIENT_ID = os.getenv('ZOHO_CLIENT_ID', '1000.KNZF8MGNSLXKAHTVVAJEWGHULJUAFC')
CLIENT_SECRET = os.getenv('ZOHO_CLIENT_SECRET', '44cbd99a7162c923b33b5cf0365e53c4ab5862d160')
REFRESH_TOKEN = os.getenv('ZOHO_REFRESH_TOKEN', '1000.db34a50cdd2603c0fa0438ab9e77f25a.a300ece5a9c25ab764db4268680d51fe')
ORG_ID = os.getenv('ZOHO_ORG_ID', '')
DC = os.getenv('ZOHO_DC', 'com')

BASE = f'https://accounts.zoho.{DC}'
CRM = f'https://www.zohoapis.{DC}/crm/v3'
BOOKS = f'https://www.zohoapis.{DC}/books/v3'
INV = f'https://www.zohoapis.{DC}/inventory/v1'
MAIL = f'https://mail.zoho.{DC}/api'

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
                    Tool(name='zoho_inventory_orders', description='List sales ord
