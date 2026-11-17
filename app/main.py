import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./haven.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
JWT_SECRET = os.getenv("JWT_SECRET", "local-only-change-this-secret-before-deploying-123456789")
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters")
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 12

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="owner")
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Property(Base):
    __tablename__ = "properties"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(300), default="")
    city: Mapped[str] = mapped_column(String(100), default="Hyderabad")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    floors: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    number: Mapped[str] = mapped_column(String(30))
    floor: Mapped[int] = mapped_column(Integer, default=1)
    room_type: Mapped[str] = mapped_column(String(40), default="Double")
    beds: Mapped[int] = mapped_column(Integer, default=2)
    monthly_rent: Mapped[float] = mapped_column(Float, default=6000)
    status: Mapped[str] = mapped_column(String(30), default="available")
    meter_type: Mapped[str] = mapped_column(String(30), default="shared")
    current_reading: Mapped[float] = mapped_column(Float, default=0)

class Resident(Base):
    __tablename__ = "residents"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(140))
    phone: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(180), default="")
    gender: Mapped[str] = mapped_column(String(30), default="Not specified")
    bed_label: Mapped[str] = mapped_column(String(30), default="Bed 1")
    monthly_rent: Mapped[float] = mapped_column(Float, default=6000)
    deposit: Mapped[float] = mapped_column(Float, default=0)
    joined_on: Mapped[str] = mapped_column(String(20), default="")
    due_day: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(30), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")

class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    resident_id: Mapped[int | None] = mapped_column(ForeignKey("residents.id"), nullable=True)
    resident_name: Mapped[str] = mapped_column(String(140), default="")
    amount: Mapped[float] = mapped_column(Float)
    payment_for: Mapped[str] = mapped_column(String(80), default="Rent")
    method: Mapped[str] = mapped_column(String(40), default="UPI")
    reference: Mapped[str] = mapped_column(String(100), default="")
    paid_on: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(30), default="paid")
    note: Mapped[str] = mapped_column(Text, default="")

class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    resident_id: Mapped[int | None] = mapped_column(ForeignKey("residents.id"), nullable=True)
    resident_name: Mapped[str] = mapped_column(String(140), default="")
    room_number: Mapped[str] = mapped_column(String(30), default="")
    title: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(60), default="Maintenance")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(60), default="Cleaning")
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    due_date: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")

class ElectricityReading(Base):
    __tablename__ = "electricity_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    previous_reading: Mapped[float] = mapped_column(Float, default=0)
    current_reading: Mapped[float] = mapped_column(Float, default=0)
    rate_per_unit: Mapped[float] = mapped_column(Float, default=8)
    billing_month: Mapped[str] = mapped_column(String(20), default="")
    amount: Mapped[float] = mapped_column(Float, default=0)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Haven PG Operations", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
security = HTTPBearer(auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def create_token(user: User) -> str:
    payload = {"sub": str(user.id), "role": user.role, "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Sign in required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Account unavailable")
    return user

def property_access(db: Session, user: User, property_id: int):
    prop = db.get(Property, property_id)
    if not prop or (user.role != "owner" and user.property_id != property_id) or (user.role == "owner" and prop.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

def seed_demo():
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == "owner@haven.demo").first():
            return
        owner = User(name="Aarav Mehta", email="owner@haven.demo", password_hash=hash_password("HavenDemo2026!"), role="owner")
        db.add(owner); db.flush()
        prop = Property(name="Greenview Residency", address="Madhapur, Hyderabad", city="Hyderabad", owner_id=owner.id, floors=3)
        db.add(prop); db.flush(); owner.property_id = prop.id
        rooms = []
        for floor in range(1, 4):
            for n in range(1, 7):
                room = Room(property_id=prop.id, number=f"{floor}{n:02d}", floor=floor, room_type="Triple" if n % 3 == 0 else "Double", beds=3 if n % 3 == 0 else 2, monthly_rent=7500 if n % 3 == 0 else 6200, status="occupied" if n < 5 else "available", meter_type="individual" if n % 2 == 0 else "shared", current_reading=round(1200 + floor*93 + n*17.5, 1))
                db.add(room); rooms.append(room)
        db.flush()
        people = [
            ("Ishita Roy","9876501201","101","Bed 1",6200,12000),("Rohan Das","9876501202","101","Bed 2",6200,12000),
            ("Priya Nair","9876501203","102","Bed 1",6200,10000),("Aditya Sen","9876501204","102","Bed 2",6200,10000),
            ("Kavya Sharma","9876501205","103","Bed 1",7500,15000),("Arjun Rao","9876501206","103","Bed 2",7500,15000),
            ("Meera Iyer","9876501207","201","Bed 1",6200,10000),("Kabir Khan","9876501208","202","Bed 1",6200,10000),
            ("Ananya Bose","9876501209","301","Bed 1",6200,10000)
        ]
        residents=[]
        for name,phone,room_no,bed,rent,deposit in people:
            room=next(r for r in rooms if r.number==room_no)
            resident=Resident(property_id=prop.id,room_id=room.id,name=name,phone=phone,bed_label=bed,monthly_rent=rent,deposit=deposit,joined_on="2026-08-01",due_day=5,status="active")
            db.add(resident); residents.append(resident)
        db.flush()
        for i,r in enumerate(residents[:7]):
            db.add(Payment(property_id=prop.id,resident_id=r.id,resident_name=r.name,amount=r.monthly_rent,payment_for="November rent",method="UPI" if i%2==0 else "Bank transfer",reference=f"DEMOUPI{i+301}",paid_on="2026-11-03",status="paid"))
        db.add(Payment(property_id=prop.id,resident_id=residents[7].id,resident_name=residents[7].name,amount=3000,payment_for="November rent (partial)",method="Cash",reference="DEMO-CASH-08",paid_on="2026-11-04",status="partial"))
        db.add_all([
            Complaint(property_id=prop.id,resident_id=residents[0].id,resident_name=residents[0].name,room_number="101",title="Bathroom tap leaking",category="Plumbing",priority="high",status="in_progress",assigned_to="Ramesh",description="Tap continues dripping after closing."),
            Complaint(property_id=prop.id,resident_id=residents[2].id,resident_name=residents[2].name,room_number="102",title="Wi-Fi signal weak",category="Internet",priority="medium",status="open",assigned_to="IT support",description="Signal drops near the study desk."),
            Complaint(property_id=prop.id,resident_id=residents[4].id,resident_name=residents[4].name,room_number="103",title="Ceiling light not working",category="Electrical",priority="low",status="resolved",assigned_to="Ramesh",description="LED driver replaced.")
        ])
        db.add_all([
            Task(property_id=prop.id,title="Clean common kitchen",category="Cleaning",assigned_to="Sunita",due_date="2026-11-17",status="in_progress",notes="Wipe counters and mop floor"),
            Task(property_id=prop.id,title="Inspect fire extinguishers",category="Safety",assigned_to="Ramesh",due_date="2026-11-18",status="pending",notes="Check expiry and pressure gauge"),
            Task(property_id=prop.id,title="Deep clean room 204",category="Cleaning",assigned_to="Sunita",due_date="2026-11-17",status="done",notes="Before new check-in")
        ])
        db.add_all([
            ElectricityReading(property_id=prop.id,room_id=rooms[1].id,previous_reading=1320,current_reading=1394,rate_per_unit=8,billing_month="2026-11",amount=592),
            ElectricityReading(property_id=prop.id,room_id=rooms[3].id,previous_reading=1180,current_reading=1245,rate_per_unit=8,billing_month="2026-11",amount=520)
        ])
        manager=User(name="Neha Kapoor",email="manager@haven.demo",password_hash=hash_password("HavenDemo2026!"),role="manager",property_id=prop.id)
        tenant=User(name="Ishita Roy",email="tenant@haven.demo",password_hash=hash_password("HavenDemo2026!"),role="tenant",property_id=prop.id)
        db.add_all([manager,tenant]); db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if os.getenv("DEMO_MODE", "true").lower() == "true":
    seed_demo()

RESOURCE_MODELS = {
    "properties": Property, "rooms": Room, "residents": Resident, "payments": Payment,
    "complaints": Complaint, "tasks": Task, "electricity": ElectricityReading
}
READ_ONLY_FIELDS = {"id","owner_id","created_at","password_hash"}
TENANT_READ_ONLY = {"properties","rooms","residents","payments","complaints","tasks","electricity"}

class LoginBody(BaseModel):
    email: str
    password: str

@app.get("/", response_class=HTMLResponse)
def home():
    with open("app/static/index.html", encoding="utf-8") as f:
        return f.read()

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status":"ok","app":"haven","database":"connected"}

@app.post("/api/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == body.email.lower()).first()
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return {"access_token":create_token(user),"token_type":"bearer","user":{"id":user.id,"name":user.name,"email":user.email,"role":user.role,"property_id":user.property_id}}

@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id":user.id,"name":user.name,"email":user.email,"role":user.role,"property_id":user.property_id}

@app.get("/api/bootstrap")
def bootstrap(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "owner":
        props = db.query(Property).filter(Property.owner_id == user.id).all()
    else:
        props = db.query(Property).filter(Property.id == user.property_id).all()
    prop_ids=[p.id for p in props]
    result={}
    for key,model in RESOURCE_MODELS.items():
        if key=="properties":
            rows=props
        else:
            rows=db.query(model).filter(model.property_id.in_(prop_ids)).all() if prop_ids else []
        result[key]=[{c.name:getattr(row,c.name) for c in model.__table__.columns if c.name not in READ_ONLY_FIELDS} | {"id":row.id} for row in rows]
    result["user"]={"id":user.id,"name":user.name,"email":user.email,"role":user.role}
    result["demo_mode"]=os.getenv("DEMO_MODE","true").lower()=="true"
    return result

@app.get("/api/{resource}")
def list_resource(resource: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    model=RESOURCE_MODELS.get(resource)
    if not model: raise HTTPException(404,"Unknown resource")
    if resource=="properties":
        rows=db.query(Property).filter(Property.owner_id==user.id).all() if user.role=="owner" else db.query(Property).filter(Property.id==user.property_id).all()
    else:
        if user.role=="owner":
            ids=[p.id for p in db.query(Property.id).filter(Property.owner_id==user.id).all()]
        else: ids=[user.property_id] if user.property_id else []
        rows=db.query(model).filter(model.property_id.in_(ids)).all() if ids else []
    return [{c.name:getattr(row,c.name) for c in model.__table__.columns if c.name not in READ_ONLY_FIELDS} | {"id":row.id} for row in rows]

@app.post("/api/{resource}")
def create_resource(resource: str, payload: dict[str,Any], db: Session=Depends(get_db), user: User=Depends(current_user)):
    if user.role=="tenant": raise HTTPException(403,"Tenant accounts cannot create or change records")
    model=RESOURCE_MODELS.get(resource)
    if not model: raise HTTPException(404,"Unknown resource")
    property_id=int(payload.get("property_id") or user.property_id or 0)
    if resource=="properties":
        if user.role!="owner": raise HTTPException(403,"Only owners can create properties")
        payload["owner_id"]=user.id
    else:
        property_access(db,user,property_id)
        payload["property_id"]=property_id
    allowed={c.name for c in model.__table__.columns}-{ "id","created_at"}
    values={k:v for k,v in payload.items() if k in allowed}
    row=model(**values)
    db.add(row); db.commit(); db.refresh(row)
    return {c.name:getattr(row,c.name) for c in model.__table__.columns if c.name not in READ_ONLY_FIELDS} | {"id":row.id}

@app.patch("/api/{resource}/{item_id}")
def update_resource(resource: str, item_id: int, payload: dict[str,Any], db: Session=Depends(get_db), user: User=Depends(current_user)):
    if user.role=="tenant": raise HTTPException(403,"Tenant accounts cannot change records")
    model=RESOURCE_MODELS.get(resource)
    if not model: raise HTTPException(404,"Unknown resource")
    row=db.get(model,item_id)
    if not row: raise HTTPException(404,"Record not found")
    if resource=="properties":
        if user.role!="owner" or row.owner_id!=user.id: raise HTTPException(404,"Property not found")
    else:
        property_access(db,user,row.property_id)
    allowed={c.name for c in model.__table__.columns}-{ "id","created_at","owner_id","property_id"}
    for key,value in payload.items():
        if key in allowed: setattr(row,key,value)
    db.commit(); db.refresh(row)
    return {c.name:getattr(row,c.name) for c in model.__table__.columns if c.name not in READ_ONLY_FIELDS} | {"id":row.id}

@app.delete("/api/{resource}/{item_id}")
def delete_resource(resource: str, item_id: int, db: Session=Depends(get_db), user: User=Depends(current_user)):
    if user.role!="owner": raise HTTPException(403,"Only owners can delete records")
    model=RESOURCE_MODELS.get(resource)
    if not model: raise HTTPException(404,"Unknown resource")
    row=db.get(model,item_id)
    if not row: raise HTTPException(404,"Record not found")
    if resource=="properties":
        if user.role!="owner" or row.owner_id!=user.id: raise HTTPException(404,"Property not found")
    else:
        property_access(db,user,row.property_id)
    db.delete(row); db.commit()
    return {"deleted":True}

@app.get("/api/dashboard")
def dashboard(db: Session=Depends(get_db), user: User=Depends(current_user)):
    ids=[p.id for p in db.query(Property.id).filter(Property.owner_id==user.id).all()] if user.role=="owner" else ([user.property_id] if user.property_id else [])
    if not ids: return {"properties":0,"rooms":0,"occupied":0,"residents":0,"collected":0,"open_complaints":0,"occupancy":0}
    rooms=db.query(Room).filter(Room.property_id.in_(ids)).all()
    residents=db.query(Resident).filter(Resident.property_id.in_(ids),Resident.status=="active").all()
    payments=db.query(Payment).filter(Payment.property_id.in_(ids),Payment.status.in_(["paid","partial"])).all()
    complaints=db.query(Complaint).filter(Complaint.property_id.in_(ids),Complaint.status!="resolved").count()
    occupied=sum(1 for r in rooms if r.status=="occupied")
    return {"properties":len(ids),"rooms":len(rooms),"occupied":occupied,"residents":len(residents),"collected":sum(p.amount for p in payments),"open_complaints":complaints,"occupancy":round(occupied/len(rooms)*100) if rooms else 0}

