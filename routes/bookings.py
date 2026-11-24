from datetime import date
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,insert,update
from database.connection import get_session,transaction
from models.tables import bookings,properties,clients,deals
from models.schemas import BookingData
from routes.users import current_user
from routes.common import rows,one,own,require,new_id,log,ensure,now

booking_router=APIRouter(prefix='/bookings',tags=['Бронирования'])
@booking_router.get('/')
def list_bookings(u=Depends(current_user),db=Depends(get_session)):
    q=select(bookings).order_by(bookings.c.id.desc())
    if u['role']=='client': q=q.where(bookings.c.clientId==u['clientId'])
    return rows(db,q)
@booking_router.get('/{booking_id}')
def get_booking(booking_id: str,u=Depends(current_user),db=Depends(get_session)):
    b=one(db,bookings,booking_id);own(u,b);return b

def reserve(db,object_id,booking_id):
    o=one(db,properties,object_id);ensure(o['status']=='Свободен','Объект уже недоступен')
    db.execute(update(properties).where(properties.c.id==object_id).values(status='Забронирован'))
    db.execute(update(bookings).where(bookings.c.objectId==object_id,bookings.c.id!=booking_id,bookings.c.status=='Ожидает подтверждения').values(status='Отклонена'))

@booking_router.post('/',status_code=201)
def create_booking(body: BookingData,u=Depends(current_user),db=Depends(get_session)):
    require(u,'manager','client')
    if body.date<date.today(): raise HTTPException(422,'Срок бронирования не может быть в прошлом')
    client_id=u['clientId'] if u['role']=='client' else body.clientId
    if not client_id: raise HTTPException(422,'Выберите клиента')
    if u['role']=='client' and body.clientId not in (None,client_id): raise HTTPException(403,'Недостаточно прав')
    with transaction(db):
        one(db,clients,client_id);o=one(db,properties,body.objectId)
        ensure(o['status']=='Свободен','Объект уже недоступен')
        ensure(not db.execute(select(bookings.c.id).where(bookings.c.objectId==body.objectId,bookings.c.clientId==client_id,bookings.c.status=='Ожидает подтверждения')).first(),'Заявка уже существует')
        bid=new_id(db,bookings,'Б-')
        item=dict(id=bid,objectId=body.objectId,clientId=client_id,date=body.date.isoformat(),status='Действует' if u['role']=='manager' else 'Ожидает подтверждения',comment=body.comment,created_at=now())
        if u['role']=='manager': reserve(db,body.objectId,bid)
        db.execute(insert(bookings).values(**item));log(db,u,'Создано бронирование',bid)
    return item

@booking_router.post('/{booking_id}/{action}')
def booking_action(booking_id: str,action: str,u=Depends(current_user),db=Depends(get_session)):
    with transaction(db):
        b=one(db,bookings,booking_id);own(u,b)
        if action=='confirm':
            require(u,'manager');ensure(b['status']=='Ожидает подтверждения','Заявка уже обработана')
            ensure(b['date']>=date.today().isoformat(),'Срок заявки истёк')
            reserve(db,b['objectId'],booking_id);status='Действует'
        elif action=='reject':
            require(u,'manager');ensure(b['status']=='Ожидает подтверждения','Заявка уже обработана');status='Отклонена'
        elif action=='cancel':
            require(u,'manager','client')
            if u['role']=='client': ensure(b['status']=='Ожидает подтверждения','Отмену действующей брони согласуйте с менеджером')
            ensure(b['status'] in ('Действует','Ожидает подтверждения'),'Бронирование уже закрыто')
            ensure(not db.execute(select(deals.c.id).where(deals.c.bookingId==booking_id)).first(),'По бронированию оформлена сделка')
            if b['status']=='Действует': db.execute(update(properties).where(properties.c.id==b['objectId']).values(status='Свободен'))
            status='Отменена'
        else: raise HTTPException(404,'Операция не найдена')
        db.execute(update(bookings).where(bookings.c.id==booking_id).values(status=status));log(db,u,'Бронирование: '+status,booking_id)
    return one(db,bookings,booking_id)
