import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime, timezone

_turso_url = os.getenv("TURSO_DATABASE_URL")
_turso_token = os.getenv("TURSO_AUTH_TOKEN")

if _turso_url and _turso_token:
    # Production: Turso (libSQL)
    _url = _turso_url.replace("libsql://", "sqlite+libsql://")
    DATABASE_URL = f"{_url}?authToken={_turso_token}&secure=true"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Local development: SQLite file
    _db_path = os.path.join(os.path.dirname(__file__), '..', 'charts.db')
    DATABASE_URL = f"sqlite:///{os.path.abspath(_db_path)}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class SavedChart(Base):
    __tablename__ = "saved_charts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False)
    name = Column(String, nullable=True)
    birth_year = Column(Integer, nullable=False)
    birth_month = Column(Integer, nullable=False)
    birth_day = Column(Integer, nullable=False)
    birth_hour = Column(Integer, nullable=False)
    birth_minute = Column(Integer, nullable=False)
    location_name = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    tz_str = Column(String, nullable=False)
    house_system = Column(String, nullable=False)
    language = Column(String, nullable=False)
    chart_data = Column(Text, nullable=True)
    svg_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
