import hashlib, os, secrets, time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, insert, delete, update
from database.connection import get_session, transaction
from models.tables import users, sessions
from models.schemas import SignIn, PasswordChange
from passwords import verify_password, hash_password
from routes.common import log

user_router=APIRouter(prefix='/user',tags=['Доступ'])
COOKIE='crm_session'
TTL=8*60*60

def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def public(u): return {k:u[k] for k in ('id','login','name','role','clientId')}
def current_user(request: Request, db=Depends(get_session)):
    token=request.cookies.get(COOKIE)
    if not token: raise HTTPException(401,'Войдите в систему')
    u=db.execute(select(users).join(sessions,sessions.c.user_id==users.c.id).where(sessions.c.token_hash==digest(token),sessions.c.expires>int(time.time()))).mappings().first()
    if u is None: raise HTTPException(401,'Сессия истекла. Войдите снова')
    return dict(u)

@user_router.post('/signin')
def signin(body: SignIn, response: Response, db=Depends(get_session)):
    login=(body.login or body.email or '').lower()
    u=db.execute(select(users).where(users.c.login==login)).mappings().first()
    if not u or not verify_password(body.password,u['password_hash']):
        raise HTTPException(401,'Неверный логин или пароль')
    token=secrets.token_urlsafe(32)
    with transaction(db):
        db.execute(delete(sessions).where(sessions.c.expires<=int(time.time())))
        db.execute(insert(sessions).values(token_hash=digest(token),user_id=u['id'],expires=int(time.time())+TTL))
        log(db,u,'Вход в систему',u['login'])
    response.set_cookie(COOKIE,token,httponly=True,samesite='strict',secure=os.getenv('CRM_SECURE_COOKIE')=='1',max_age=TTL,path='/')
    return public(u)

@user_router.get('/me')
def me(u=Depends(current_user)): return public(u)

@user_router.post('/signout')
def signout(request: Request,response: Response,db=Depends(get_session)):
    token=request.cookies.get(COOKIE)
    if token:
        with transaction(db): db.execute(delete(sessions).where(sessions.c.token_hash==digest(token)))
    response.delete_cookie(COOKIE,path='/')
    return {'message':'Выход выполнен'}

@user_router.post('/password')
def change_password(body: PasswordChange,response: Response,u=Depends(current_user),db=Depends(get_session)):
    if not verify_password(body.old_password,u['password_hash']): raise HTTPException(400,'Неверный текущий пароль')
    with transaction(db):
        db.execute(update(users).where(users.c.id==u['id']).values(password_hash=hash_password(body.new_password)))
        db.execute(delete(sessions).where(sessions.c.user_id==u['id']))
        log(db,u,'Изменение пароля',u['login'])
    response.delete_cookie(COOKIE,path='/')
    return {'message':'Пароль изменён. Войдите снова'}
