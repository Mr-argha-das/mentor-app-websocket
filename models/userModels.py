from sqlalchemy import Column, String, Text, Date, DateTime, Enum
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.sql import func
from db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    full_name = Column(String(255))
    email = Column(String(255))
    phone_number = Column(String(255))
    password = Column(String(255))
    device_token = Column(String(255))
    token = Column(Text)
    profile_pic = Column(String(255))
    user_type = Column(String(255))
    student_id = Column(String(500))
    service_type = Column(String(255))
    description = Column(Text)
    skills_id = Column(String(255))
    total_experience = Column(String(255))
    users_field = Column(String(255))
    language_known = Column(String(255))
    linkedin_user = Column(String(255))
    dob = Column(Date)
    gender = Column(Enum("male", "female", "other"))
    resume_upload = Column(String(255))
    status = Column(String(255))
    coins = Column(String(255), default="0")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
