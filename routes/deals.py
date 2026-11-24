from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import Response
from sqlalchemy import select,insert,update
from database.connection import get_session,transaction
from models.tables import deals,bookings,properties,clients
from models.schemas import DealData,ActionData
from routes.users import current_user
from routes.common import rows,one,own,require,new_id,log,ensure,now
import html

deal_router=APIRouter(prefix='/deals',tags=['Сделки и документы'])
@deal_router.get('/')
def list_deals(u=Depends(current_user),db=Depends(get_session)):
    q=select(deals).order_by(deals.c.id.desc())
    if u['role']=='client': q=q.where(deals.c.clientId==u['clientId'])
    return rows(db,q)
@deal_router.get('/{deal_id}')
def get_deal(deal_id: str,u=Depends(current_user),db=Depends(get_session)):
    d=one(db,deals,deal_id);own(u,d);return d
@deal_router.post('/',status_code=201)
def create_deal(body: DealData,u=Depends(current_user),db=Depends(get_session)):
    require(u,'manager')
    with transaction(db):
        b=one(db,bookings,body.bookingId);o=one(db,properties,b['objectId'])
        ensure(b['status']=='Действует' and o['status']=='Забронирован','Требуется действующее бронирование')
        ensure(not db.execute(select(deals.c.id).where(deals.c.bookingId==b['id'])).first(),'Сделка уже существует')
        d=dict(id=new_id(db,deals,'С-'),objectId=o['id'],clientId=b['clientId'],bookingId=b['id'],payment=body.payment,status='Подготовка договора',sent=False,signed=False,bank='Не запрашивался',registration='Не запрошена',price=o['price'],created_at=now())
        db.execute(insert(deals).values(**d));log(db,u,'Создана сделка',d['id'])
    return one(db,deals,d['id'])

@deal_router.post('/{deal_id}/action/{action}')
def deal_action(deal_id: str,action: str,body: ActionData,u=Depends(current_user),db=Depends(get_session)):
    with transaction(db):
        d=one(db,deals,deal_id);own(u,d);v={}
        if action=='sign-contract':
            require(u,'client');ensure(d['sent'] and not d['signed'] and d['status']=='Ожидает подписания','Договор недоступен для подтверждения')
            v=dict(signed=True,confirmed_at=now(),status='Подписан')
        else:
            require(u,'manager')
            if action in ('register-deal','register-done'):
                ensure(d['status']=='Завершена','Сделка ещё не завершена')
                ensure(bool(body.note),'Укажите основание изменения статуса')
                if action=='register-deal':
                    ensure(d['registration']=='Не запрошена','Статус регистрации уже изменён');v=dict(registration='На регистрации',registration_note=body.note)
                else:
                    ensure(d['registration']=='На регистрации','Регистрация не начата');v=dict(registration='Завершена регистрация',registration_note=body.note)
            else:
                ensure(d['status']!='Завершена','Сделка завершена')
                if action=='send-contract':
                    ensure(not d['sent'],'Договор уже отправлен');v=dict(sent=True,status='Ожидает подписания')
                elif action=='bank-request':
                    ensure(d['signed'] and d['bank'] in ('Не запрашивался','Отказ банка'),'Требуется подтверждение договора и отсутствие активного запроса')
                    v=dict(bank='На рассмотрении',status='Подписан',bank_note=body.note)
                elif action in ('bank-ok','bank-no'):
                    ensure(d['signed'] and d['bank']=='На рассмотрении','Нет запроса на рассмотрении')
                    ensure(bool(body.note),'Укажите основание решения банка или подтверждения расчётов')
                    v=dict(bank='Одобрено' if action=='bank-ok' else 'Отказ банка',status='Подписан' if action=='bank-ok' else 'Приостановлена',bank_note=body.note)
                elif action=='change-payment':
                    ensure(d['bank']=='Отказ банка' or not d['sent'],'Изменение оплаты доступно до отправки договора или после отказа')
                    ensure(body.payment is not None and body.payment!=d['payment'],'Выберите другой способ оплаты')
                    v=dict(payment=body.payment,sent=False,signed=False,confirmed_at=None,bank='Не запрашивался',bank_note='',status='Подготовка договора')
                elif action=='finish-deal':
                    ensure(d['signed'] and d['bank']=='Одобрено','Требуются подтверждение договора и расчётов')
                    b=one(db,bookings,d['bookingId']);o=one(db,properties,d['objectId']);ensure(b['status']=='Действует' and o['status']=='Забронирован','Бронирование недействительно')
                    db.execute(update(properties).where(properties.c.id==o['id']).values(status='Продано'))
                    db.execute(update(bookings).where(bookings.c.id==b['id']).values(status='Завершено'))
                    v=dict(status='Завершена',completed_at=now())
                else: raise HTTPException(404,'Операция не найдена')
        db.execute(update(deals).where(deals.c.id==deal_id).values(**v));log(db,u,'Сделка: '+action,deal_id)
    return one(db,deals,deal_id)

@deal_router.get('/{deal_id}/document')
def document(deal_id: str,u=Depends(current_user),db=Depends(get_session)):
    d=one(db,deals,deal_id);own(u,d)
    if u['role']=='client' and not d['sent']: raise HTTPException(404,'Документ пока недоступен')
    c=one(db,clients,d['clientId']);o=one(db,properties,d['objectId']);e=lambda s:html.escape(str(s))
    lines=[('Номер сделки',d['id']),('Объект',o['title']),('Адрес',o['address']),('Покупатель',c['name']),('Стоимость',f"{d['price']:,} ₽".replace(',',' ')),('Способ оплаты',d['payment']),('Состояние',d['status']),('Подтверждение условий',d['confirmed_at'] or 'Не получено')]
    content='<!doctype html><html lang="ru"><meta charset="utf-8"><title>Карточка договора</title><style>body{font:16px Arial;max-width:700px;margin:50px auto;line-height:1.6}h1{font-size:24px}dt{font-weight:bold}dd{margin:0 0 12px}</style><h1>Карточка договора купли-продажи</h1><dl>'+''.join(f'<dt>{e(k)}</dt><dd>{e(v)}</dd>' for k,v in lines)+'</dl><p>Внутренняя карточка условий. Не заменяет подписанный сторонами юридический договор или квалифицированную электронную подпись.</p></html>'
    return Response(content,media_type='text/html',headers={'Content-Disposition':'attachment; filename="contract-'+str(d['id'].split('-')[-1])+'.html"'})
