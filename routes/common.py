from datetime import datetime, timezone
from sqlalchemy import select, insert
from fastapi import HTTPException
from models.tables import activity

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def rows(db, statement): return [dict(x) for x in db.execute(statement).mappings()]
def one(db, table, key):
    r = db.execute(select(table).where(table.c.id == key)).mappings().first()
    if r is None: raise HTTPException(404, 'Запись не найдена')
    return dict(r)
def require(user, *roles):
    if user['role'] not in roles: raise HTTPException(403, 'Недостаточно прав')
def own(user, record):
    if user['role']=='client' and record['clientId']!=user['clientId']:
        raise HTTPException(404,'Запись не найдена')
def ensure(ok, msg):
    if not ok: raise HTTPException(409,msg)
def new_id(db, table, prefix):
    # All callers hold a write transaction. No deletion of numbered records.
    ids = db.execute(select(table.c.id)).scalars().all()
    n = max([int(i[len(prefix):]) for i in ids if i.startswith(prefix) and i[len(prefix):].isdigit()] or [0])+1
    return f'{prefix}{n:03d}'
def log(db,user,action,target):
    db.execute(insert(activity).values(user_id=user['id'],action=action,target=target,at=now()))
