from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from database.connection import conn
from routes.users import user_router
from routes.catalog import catalog_router
from routes.clients import client_router
from routes.bookings import booking_router
from routes.deals import deal_router
from routes.reports import report_router
from seed import seed

@asynccontextmanager
async def lifespan(app):
    conn();seed();yield

app=FastAPI(title='CRM отдела продаж недвижимости',version='2.0.0',lifespan=lifespan)
for router in (user_router,catalog_router,client_router,booking_router,deal_router,report_router):app.include_router(router)
WEB=Path(__file__).parent/'web'
app.mount('/static',StaticFiles(directory=WEB),name='static')
@app.middleware('http')
async def security(request: Request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if request.headers.get('sec-fetch-site')=='cross-site' or (origin and urlsplit(origin).netloc!=request.headers.get('host')):
            return JSONResponse({'detail':'Недопустимый источник запроса'},status_code=403)
    r=await call_next(request)
    r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY'
    if not request.url.path.startswith('/static/'):
        r.headers['Cache-Control']='no-store'
    return r
@app.get('/',include_in_schema=False)
@app.get('/web/',include_in_schema=False)
def home(): return FileResponse(WEB/'index.html')
