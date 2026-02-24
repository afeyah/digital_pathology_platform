# File: app/database/create_database.py
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
import bcrypt
from app.database.models import Base, User, Patient, WSI, Report, ROI, Heatmap, UserRole

# --- Configuration ---

DATABASE_URL = "sqlite:///digital_pathology.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Models ---

class Setting(Base):

    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    wsi_storage_path = Column(String, nullable=True)

# --- Database Utilities ---

def init_db():

    Base.metadata.create_all(bind=engine)
    print("Database structure initialized successfully!")

def hash_password(plain_password: str) -> str:

    password_bytes = plain_password.encode('utf-8') 
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:

    password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_password_bytes)

def create_initial_users():

    db = SessionLocal()
    try:
        if not db.query(User).filter_by(username="admin").first():
            admin = User(
                name="Super Admin",
                username="admin",
                password=hash_password("admin"), 
                role=UserRole.ADMIN
            )
            db.add(admin)
            db.commit()
            print("Default admin created (Username: admin / Password: admin)")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    create_initial_users()