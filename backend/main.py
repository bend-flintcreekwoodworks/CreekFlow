from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db
from models import Base, User
from database import engine
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Define request model for login
class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/")
def home():
    return {"message": "CreekFlow API is running"}

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# New authentication route: Login users using MySQL
@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or user.password != request.password:  # Later, replace with password hashing
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"message": "Login successful"}
