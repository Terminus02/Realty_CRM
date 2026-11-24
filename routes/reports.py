import csv,io
from fastapi import APIRouter,Depends
from fastapi.responses import Response
from sqlalchemy import select
from database.connection import get_session
from models.tables import deals,properties,bookings,clients,activity,users
from routes.users import current_user
from routes.common import rows,require
report_router=APIRouter(prefix='/reports',tags=['Отчёты'])

def summary(db,segment=None):
    p=rows(db,select(properties)); ids={x['id'] for x in p if not segment or x['type']==segment}; ds=[x for x in rows(db,select(deals)) if x['objectId'] in ids]; bs=[x for x in rows(db,select(bookings)) if x['objectId'] in ids]; sold=[x for x in ds if x['status']=='Завершена']
    return dict(revenue=sum(x['price'] for x in sold),completed=len(sold),open=len(ds)-len(sold),mortgage=sum(x['payment']=='Ипотека' for x in ds),active_bookings=sum(x['status']=='Действует' for x in bs),pending_bookings=sum(x['status']=='Ожидает подтверждения' for x in bs),conversion=round(len(sold)/len(ds)*100,1) if ds else 0,segments=[{'type':t,'count':sum(x['type']==t and x['id'] in ids for x in p),'sold':sum(x['objectId'] in {y['id'] for y in p if y['type']==t} for x in sold)} for t in ['Квартира','Машино-место','Коммерческий объект']])
@report_router.get('/')
def report(segment: str|None=None,u=Depends(current_user),db=Depends(get_session)):
    require(u,'director'); return summary(db,segment)
@report_router.get('/export')
def export(segment: str|None=None,u=Depends(current_user),db=Depends(get_session)):
    require(u,'director');s=summary(db,segment);out=io.StringIO();w=csv.writer(out,delimiter=';');w.writerow(['Показатель','Значение']);
    for label,k in [('Выручка по закрытым сделкам, ₽','revenue'),('Завершено','completed'),('В работе','open'),('Ипотечные сделки','mortgage'),('Действующие бронирования','active_bookings'),('Заявки','pending_bookings'),('Доля завершённых сделок, %','conversion')]:w.writerow([label,s[k]])
    return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="sales.csv"'})
@report_router.get('/activity')
def audit(u=Depends(current_user),db=Depends(get_session)):
    require(u,'director');return rows(db,select(activity.c.at,activity.c.action,activity.c.target,users.c.name).join(users,users.c.id==activity.c.user_id).order_by(activity.c.id.desc()).limit(100))
