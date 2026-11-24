import json,os
from pathlib import Path
from datetime import date,timedelta
from sqlalchemy import select,insert
from database.connection import conn,engine,transaction
from models.tables import users,clients,properties,bookings,deals
from passwords import hash_password
from routes.common import now

ACCOUNTS=[('director','Руководитель отдела','director',None,'Director2026!'),('manager','Менеджер по продажам','manager',None,'Manager2026!'),('client','Иванов Алексей П.','client','КЛ-001','Client2026!')]
def seed():
    conn()
    with engine.connect() as db, transaction(db):
        if db.execute(select(users.c.id).limit(1)).first(): return False
        data=json.loads((Path(__file__).parent/'database'/'initial_data.json').read_text(encoding='utf-8'))
        for c in data['clients']:db.execute(insert(clients).values(**c))
        for o in data['objects']:
            db.execute(insert(properties).values(**o,description=f"{o['type']} по адресу {o['address']}. Площадь {o['area']} м²."))
        for b in data['bookings']:
            b['date']=(date.today()+timedelta(days=14)).isoformat();db.execute(insert(bookings).values(**b,created_at=now()))
        for d in data['deals']:
            d['bank']='Не запрашивался';d['price']=next(o['price'] for o in data['objects'] if o['id']==d['objectId']);d['created_at']=now();db.execute(insert(deals).values(**d))
        # Preserve the original sold parking space as an available historical record for reporting.
        b=dict(id='Б-103',objectId='ММ-031',clientId='КЛ-003',date=date.today().isoformat(),status='Завершено',comment='Архивная продажа',created_at=now())
        db.execute(insert(bookings).values(**b));db.execute(insert(deals).values(id='С-080',objectId=b['objectId'],clientId=b['clientId'],bookingId=b['id'],payment='Собственные средства',status='Завершена',sent=True,signed=True,bank='Одобрено',registration='Не запрошена',price=1600000,created_at=now(),completed_at=now(),confirmed_at=now(),bank_note='Архивная запись'))
        for login,name,role,cid,password in ACCOUNTS:
            pw=os.getenv('CRM_PASSWORD_'+role.upper(),password)
            db.execute(insert(users).values(login=login,name=name,role=role,clientId=cid,password_hash=hash_password(pw)))
    return True
if __name__=='__main__':print('База данных подготовлена' if seed() else 'База уже инициализирована; данные сохранены')
