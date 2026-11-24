from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from datetime import date

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class SignIn(StrictModel):
    login: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=1, max_length=256)

class PasswordChange(StrictModel):
    old_password: str = Field(min_length=1,max_length=256)
    new_password: str = Field(min_length=10,max_length=256)

class PropertyData(StrictModel):
    type: Literal['Квартира','Машино-место','Коммерческий объект']
    title: str = Field(min_length=1,max_length=160)
    address: str = Field(min_length=1,max_length=250)
    area: float = Field(gt=0,le=1000000)
    floor: str = Field(min_length=1,max_length=40)
    price: int = Field(gt=0,le=100000000000)
    rooms: int | None = Field(default=None, ge=0,le=100)
    description: str = Field(default='',max_length=4000)

class ClientData(StrictModel):
    name: str = Field(min_length=2,max_length=120)
    phone: str = Field(min_length=3,max_length=60)
    email: str = Field(min_length=3,max_length=120)
    comment: str = Field(default='',max_length=2000)

class BookingData(StrictModel):
    objectId: str
    clientId: str | None = None
    date: date
    comment: str = Field(default='',max_length=2000)

class DealData(StrictModel):
    bookingId: str
    payment: Literal['Ипотека','Собственные средства'] = 'Собственные средства'

class ActionData(StrictModel):
    note: str = Field(default='',max_length=2000)
    payment: Literal['Ипотека','Собственные средства'] | None = None
