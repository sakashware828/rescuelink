from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from .database import Base

class Profile(Base):
    __tablename__ = "profiles"

    device_id = Column(String, primary_key=True, index=True)
    passcode = Column(String, nullable=False)
    name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    blood_group = Column(String, nullable=True)
    emergency_contact = Column(String, nullable=True)
    govt_id_type = Column(String, nullable=True)
    govt_id_number = Column(String, nullable=True)
    medical_conditions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "passcode": self.passcode,
            "name": self.name or "",
            "age": self.age,
            "blood_group": self.blood_group or "",
            "emergency_contact": self.emergency_contact or "",
            "govt_id_type": self.govt_id_type or "",
            "govt_id_number": self.govt_id_number or "",
            "medical_conditions": self.medical_conditions or "None listed",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, index=True, nullable=True)
    trigger_type = Column(String, default="EMERGENCY")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    battery = Column(Integer, nullable=True)
    message = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "trigger_type": self.trigger_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed": self.speed,
            "battery": self.battery,
            "message": self.message,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
        }
