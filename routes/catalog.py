from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert, update
from database.connection import get_session, transaction
from models.tables import properties, bookings, deals
from models.schemas import PropertyData
from routes.users import current_user
from routes.common import rows, one, require, new_id, log, ensure

catalog_router=APIRouter(prefix='/catalog',tags=['Каталог'])

@catalog_router.get('/')
def get_catalog(u=Depends(current_user),db=Depends(get_session)):
    return rows(db,select(properties).order_by(properties.c.id))

@catalog_router.get('/{property_id}')
def get_property(property_id: str,u=Depends(current_user),db=Depends(get_session)):
    return one(db,properties,property_id)

@catalog_router.post('/',status_code=201)
def create_property(body: PropertyData,u=Depends(current_user),db=Depends(get_session)):
    require(u,'director')
    with transaction(db):
        prefix={'Квартира':'КВ-','Машино-место':'ММ-','Коммерческий объект':'КМ-'}[body.type]
        item={'id':new_id(db,properties,prefix),**body.model_dump(),'status':'Свободен'}
        db.execute(insert(properties).values(**item)); log(db,u,'Добавлен объект',item['id'])
    return item

@catalog_router.put('/{property_id}')
def edit_property(property_id: str,body: PropertyData,u=Depends(current_user),db=Depends(get_session)):
    require(u,'director')
    with transaction(db):
        old=one(db,properties,property_id)
        ensure(old['type']==body.type,'Тип существующего объекта изменить нельзя')
        ensure(old['status']=='Свободен','Редактировать можно только свободные объекты')
        db.execute(update(properties).where(properties.c.id==property_id).values(**body.model_dump()));log(db,u,'Изменён объект',property_id)
    return one(db,properties,property_id)
