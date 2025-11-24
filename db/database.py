from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "mysql+pymysql://u739347814_educations:1LUdUDly~In@srv1882.hstgr.io:3306/u739347814_educations"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,       # Fixes MySQL server has gone away
    pool_recycle=280,         # Prevents idle timeout issues
    pool_size=10,             # DB pool size
    max_overflow=20           # Extra connections under load
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False    # Prevents stale session issues
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
