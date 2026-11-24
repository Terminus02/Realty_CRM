import os
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from models.tables import metadata

DB_PATH = Path(os.environ.get('CRM_DB', Path(__file__).resolve().parents[1] / 'data' / 'crm.db')).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine('sqlite:///' + str(DB_PATH), connect_args={'check_same_thread': False, 'timeout': 15})

@event.listens_for(engine, 'connect')
def configure_sqlite(dbapi_conn, _):
    dbapi_conn.execute('PRAGMA foreign_keys=ON')
    dbapi_conn.execute('PRAGMA busy_timeout=15000')

def conn():
    metadata.create_all(engine)

def get_session():
    with engine.connect() as session:
        yield session

@contextmanager
def transaction(session):
    # SQLite serializes writers before checking availability, avoiding double booking.
    if session.in_transaction():
        session.commit()
    session.exec_driver_sql('BEGIN IMMEDIATE')
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
