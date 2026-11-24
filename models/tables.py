from sqlalchemy import MetaData, Table, Column, Integer, String, Text, Float, Boolean, ForeignKey, CheckConstraint, Index, text

metadata = MetaData()
clients = Table('clients', metadata,
    Column('id', String, primary_key=True), Column('name', String, nullable=False),
    Column('phone', String, nullable=False), Column('email', String, nullable=False),
    Column('comment', Text, nullable=False, default=''))
users = Table('users', metadata,
    Column('id', Integer, primary_key=True), Column('login', String, unique=True, nullable=False),
    Column('password_hash', String, nullable=False), Column('name', String, nullable=False),
    Column('role', String, nullable=False), Column('clientId', ForeignKey('clients.id'), unique=True),
    CheckConstraint("role IN ('director','manager','client')"),
    CheckConstraint("(role='client' AND clientId IS NOT NULL) OR (role!='client' AND clientId IS NULL)"))
sessions = Table('sessions', metadata,
    Column('token_hash', String, primary_key=True), Column('user_id', ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('expires', Integer, nullable=False))
properties = Table('properties', metadata,
    Column('id', String, primary_key=True), Column('type', String, nullable=False),
    Column('title', String, nullable=False), Column('address', String, nullable=False),
    Column('area', Float, nullable=False), Column('floor', String, nullable=False),
    Column('price', Integer, nullable=False), Column('status', String, nullable=False, default='Свободен'),
    Column('rooms', Integer), Column('description', Text, nullable=False, default=''),
    CheckConstraint('price > 0 AND area > 0'),
    CheckConstraint("status IN ('Свободен','Забронирован','Продано')"))
bookings = Table('bookings', metadata,
    Column('id', String, primary_key=True), Column('objectId', ForeignKey('properties.id'), nullable=False),
    Column('clientId', ForeignKey('clients.id'), nullable=False), Column('date', String, nullable=False),
    Column('status', String, nullable=False), Column('comment', Text, nullable=False, default=''),
    Column('created_at', String, nullable=False))
Index('unique_active_booking', bookings.c.objectId, unique=True, sqlite_where=bookings.c.status=='Действует')
deals = Table('deals', metadata,
    Column('id', String, primary_key=True), Column('objectId', ForeignKey('properties.id'), nullable=False),
    Column('clientId', ForeignKey('clients.id'), nullable=False), Column('bookingId', ForeignKey('bookings.id'), unique=True, nullable=False),
    Column('payment', String, nullable=False), Column('status', String, nullable=False),
    Column('sent', Boolean, nullable=False, default=False), Column('signed', Boolean, nullable=False, default=False),
    Column('bank', String, nullable=False), Column('registration', String, nullable=False),
    Column('price', Integer, nullable=False), Column('created_at', String, nullable=False), Column('completed_at', String),
    Column('confirmed_at', String), Column('bank_note', Text, nullable=False, default=''),
    Column('registration_note', Text, nullable=False, default=''))
activity = Table('activity', metadata,
    Column('id', Integer, primary_key=True), Column('user_id', ForeignKey('users.id'), nullable=False),
    Column('action', String, nullable=False), Column('target', String, nullable=False), Column('at', String, nullable=False))
