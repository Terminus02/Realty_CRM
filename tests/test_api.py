import os,tempfile
from pathlib import Path
from datetime import date,timedelta
import pytest
from fastapi.testclient import TestClient

# Use isolated SQLite storage, never the working CRM database.
TEMP=tempfile.TemporaryDirectory()
os.environ['CRM_DB']=str(Path(TEMP.name)/'test.db')
from main import app
from database.connection import engine
from models.tables import metadata

@pytest.fixture
def browser():
    metadata.drop_all(engine)
    with TestClient(app) as c: yield c

def login(c,role):
    c.cookies.clear()
    r=c.post('/user/signin',json={'login':role,'password':role.title()+'2026!'})
    assert r.status_code==200,r.text
    assert r.json()['role']==role
    return r

def action(c,id,a,body=None): return c.post(f'/deals/{id}/action/{a}',json=body or {})

def test_login_permissions(browser):
    c=browser
    assert c.get('/catalog/').status_code==401
    assert c.post('/user/signin',json={'login':'manager','password':'wrong'}).status_code==401
    login(c,'client'); assert len(c.get('/clients/').json())==1
    assert all(x['clientId']=='КЛ-001' for x in c.get('/bookings/').json())
    assert c.get('/bookings/Б-105').status_code==404
    assert c.get('/deals/С-082').status_code==404
    assert c.get('/deals/С-082/document').status_code==404
    assert c.get('/reports/').status_code==403
    assert c.post('/clients/',json={'name':'Name','phone':'123','email':'x@y.ru'}).status_code==403
    assert c.post('/bookings/',json={'objectId':'КВ-125','clientId':'КЛ-002','date':date.today().isoformat()}).status_code==403
    login(c,'manager');assert len(c.get('/clients/').json())==4
    assert c.get('/reports/').status_code==403
    login(c,'director');assert c.get('/reports/').status_code==200
    assert c.get('/reports/export').status_code==200
    assert c.post('/user/signout').status_code==200
    assert c.get('/user/me').status_code==401

def test_full_sale_with_bank_refusal(browser):
    c=browser;login(c,'client');date_str=(date.today()+timedelta(days=10)).isoformat()
    b=c.post('/bookings/',json={'objectId':'КВ-125','date':date_str}).json();bid=b['id']
    assert b['status']=='Ожидает подтверждения'
    assert c.get('/catalog/КВ-125').json()['status']=='Свободен'
    assert c.post(f'/bookings/{bid}/confirm').status_code==403
    login(c,'manager');assert c.post(f'/bookings/{bid}/confirm').status_code==200
    assert c.post('/bookings/',json={'objectId':'КВ-125','clientId':'КЛ-002','date':date_str}).status_code==409
    d=c.post('/deals/',json={'bookingId':bid,'payment':'Ипотека'}).json();did=d['id']
    assert action(c,did,'finish-deal').status_code==409
    assert action(c,did,'sign-contract').status_code==403
    assert action(c,did,'send-contract').status_code==200
    login(c,'client');assert c.get(f'/deals/{did}/document').status_code==200
    assert action(c,did,'sign-contract').status_code==200
    login(c,'manager');assert action(c,did,'bank-request').status_code==200
    assert action(c,did,'bank-no',{'note':'Ответ №123'}).json()['status']=='Приостановлена'
    assert c.get('/catalog/КВ-125').json()['status']=='Забронирован'
    assert action(c,did,'change-payment',{'payment':'Собственные средства'}).json()['signed'] is False
    assert action(c,did,'send-contract').status_code==200
    login(c,'client');assert action(c,did,'sign-contract').status_code==200
    login(c,'manager');assert action(c,did,'bank-request').status_code==200
    assert action(c,did,'bank-ok',{'note':'Выписка №42'}).status_code==200
    assert action(c,did,'finish-deal').json()['status']=='Завершена'
    assert c.get('/catalog/КВ-125').json()['status']=='Продано'
    assert c.get(f'/bookings/{bid}').json()['status']=='Завершено'
    assert action(c,did,'register-deal',{'note':'Заявление №12'}).status_code==200
    assert action(c,did,'register-done',{'note':'Выписка ЕГРН №12'}).json()['registration']=='Завершена регистрация'
    login(c,'director');assert c.get('/reports/').json()['revenue']==10_500_000

def test_catalog_and_clients(browser):
    c=browser;body={'type':'Квартира','title':'Новая квартира','address':'Адрес','area':45,'floor':'5','price':5000000,'rooms':2}
    login(c,'manager');assert c.post('/catalog/',json=body).status_code==403
    r=c.post('/clients/',json={'name':'Новый клиент','phone':'12345','email':'customer@example.org'});assert r.status_code==201
    cid=r.json()['id'];assert c.put('/clients/'+cid,json={'name':'Клиент','phone':'12345','email':'customer@example.org'}).status_code==200
    login(c,'director');r=c.post('/catalog/',json=body);assert r.status_code==201
    pid=r.json()['id'];body['price']=5500000;assert c.put('/catalog/'+pid,json=body).status_code==200
    assert c.get('/catalog/'+pid).json()['price']==5500000
    assert c.post('/bookings/',json={'objectId':pid,'clientId':cid,'date':date.today().isoformat()}).status_code==403

def test_password_and_session(browser):
    c=browser;login(c,'client');assert c.post('/user/password',json={'old_password':'wrong','new_password':'NewPassword!234'}).status_code==400
    assert c.post('/user/password',json={'old_password':'Client2026!','new_password':'NewPassword!234'}).status_code==200
    assert c.get('/user/me').status_code==401
    assert c.post('/user/signin',json={'login':'client','password':'Client2026!'}).status_code==401
    assert c.post('/user/signin',json={'login':'client','password':'NewPassword!234'}).status_code==200
    assert c.post('/user/signout',headers={'Origin':'https://untrusted.test'}).status_code==403

def test_concurrent_booking_and_persistence(browser):
    from concurrent.futures import ThreadPoolExecutor
    from seed import seed
    c=browser;login(c,'manager');date_str=(date.today()+timedelta(days=10)).isoformat()
    token=c.cookies.get('crm_session')
    def book(cid):
        with TestClient(app) as other:
            other.cookies.set('crm_session',token)
            return other.post('/bookings/',json={'objectId':'КВ-218','clientId':cid,'date':date_str}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(book,['КЛ-002','КЛ-003']))
    assert sorted(results)==[201,409],results
    engine.dispose()
    assert seed() is False
    assert c.get('/catalog/КВ-218').json()['status']=='Забронирован'
    assert len([b for b in c.get('/bookings/').json() if b['objectId']=='КВ-218' and b['status']=='Действует'])==1
