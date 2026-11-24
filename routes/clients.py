from fastapi import APIRouter, Depends
from sqlalchemy import select,insert,update
from database.connection import get_session, transaction
from models.tables import clients
from models.schemas import ClientData
from routes.users import current_user
from routes.common import rows, one, require, new_id, log

client_router=APIRouter(prefix='/clients',tags=['Клиенты'])
@client_router.get('/')
def list_clients(u=Depends(current_user),db=Depends(get_session)):
    q=select(clients).order_by(clients.c.id)
    if u['role']=='client': q=q.where(clients.c.id==u['clientId'])
    return rows(db,q)
@client_router.post('/',status_code=201)
def create_client(body: ClientData,u=Depends(current_user),db=Depends(get_session)):
    require(u,'manager')
    with transaction(db):
        item={'id':new_id(db,clients,'КЛ-'),**body.model_dump()}
        db.execute(insert(clients).values(**item));log(db,u,'Добавлен клиент',item['id'])
    return item
@client_router.put('/{client_id}')
def edit_client(client_id: str,body: ClientData,u=Depends(current_user),db=Depends(get_session)):
    require(u,'manager')
    with transaction(db):
        one(db,clients,client_id)
        db.execute(update(clients).where(clients.c.id==client_id).values(**body.model_dump()));log(db,u,'Изменён клиент',client_id)
    return one(db,clients,client_id)
