from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./rescuelink.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class VictimProfile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True)
    victim_name = Column(String)
    blood_group = Column(String)
    critical_allergies = Column(String)
    emergency_contact = Column(String)

class IncidentLog(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String)
    latitude = Column(String)
    longitude = Column(String)
    sos_triggered = Column(Boolean)
    received_at = Column(DateTime, default=datetime.datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()