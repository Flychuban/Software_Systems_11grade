from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from uuid import uuid4

app = FastAPI()

# OAuth2 for authentication (mocked for simplicity)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

# Mock databases
users_db = []
books_db = []
reservations_db = []
borrowings_db = []
events_db = []
overdue_db = []

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    username: str
    password: str
    email: str
    full_name: Optional[str] = None
    role: str  # "user" or "librarian"

class Book(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    author: str
    year: int
    isbn: str
    quantity: int
    available: int

class Borrowing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    book_id: str
    borrowed_at: datetime
    due_date: datetime
    returned_at: Optional[datetime] = None

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    date: datetime
    time: str
    location: str
    attendees: List[str] = []

# Dependency to get the current user
def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    user = next((u for u in users_db if u.username == token), None)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user

# User Routes
@app.post("/users/register", response_model=User)
def register_user(user: User):
    if any(u.username == user.username for u in users_db):
        raise HTTPException(status_code=400, detail="Username already exists")
    users_db.append(user)
    return user

@app.post("/users/login")
def login_user(username: str, password: str):
    user = next((u for u in users_db if u.username == username and u.password == password), None)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    return {"access_token": user.username, "token_type": "bearer"}

@app.get("/users", response_model=List[User])
def get_users(role: Optional[str] = None, current_user: User = Depends(get_current_user)):
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    return [u for u in users_db if role is None or u.role == role]

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: str, current_user: User = Depends(get_current_user)):
    user = next((u for u in users_db if u.id == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Book Routes
@app.get("/books", response_model=List[Book])
def get_books(title: Optional[str] = None, author: Optional[str] = None, year: Optional[int] = None, available: Optional[bool] = None):
    books = books_db
    if title:
        books = [b for b in books if title.lower() in b.title.lower()]
    if author:
        books = [b for b in books if author.lower() in b.author.lower()]
    if year:
        books = [b for b in books if b.year == year]
    if available is not None:
        books = [b for b in books if (b.available > 0) == available]
    return books

@app.get("/books/{book_id}", response_model=Book)
def get_book(book_id: str):
    book = next((b for b in books_db if b.id == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@app.post("/books", response_model=Book)
def add_book(book: Book, current_user: User = Depends(get_current_user)):
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    books_db.append(book)
    return book

@app.patch("/books/{book_id}", response_model=Book)
def update_book(book_id: str, book: Book, current_user: User = Depends(get_current_user)):
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    existing_book = next((b for b in books_db if b.id == book_id), None)
    if not existing_book:
        raise HTTPException(status_code=404, detail="Book not found")
    existing_book.title = book.title or existing_book.title
    existing_book.description = book.description or existing_book.description
    existing_book.author = book.author or existing_book.author
    existing_book.year = book.year or existing_book.year
    existing_book.isbn = book.isbn or existing_book.isbn
    existing_book.quantity = book.quantity or existing_book.quantity
    return existing_book

@app.delete("/books/{book_id}")
def delete_book(book_id: str, current_user: User = Depends(get_current_user)):
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    global books_db
    books_db = [b for b in books_db if b.id != book_id]
    return {"message": "Book deleted"}

# Borrowing Routes
@app.post("/books/{book_id}/borrow")
def borrow_book(book_id: str, current_user: User = Depends(get_current_user)):
    book = next((b for b in books_db if b.id == book_id), None)
    if not book or book.available <= 0:
        raise HTTPException(status_code=400, detail="Book not available")
    book.available -= 1
    borrowing = Borrowing(user_id=current_user.id, book_id=book_id, borrowed_at=datetime.utcnow(), due_date=datetime.utcnow() + timedelta(days=14))
    borrowings_db.append(borrowing)
    return borrowing

@app.post("/books/{book_id}/return")
def return_book(book_id: str, current_user: User = Depends(get_current_user)):
    borrowing = next((b for b in borrowings_db if b.book_id == book_id and b.user_id == current_user.id and not b.returned_at), None)
    if not borrowing:
        raise HTTPException(status_code=400, detail="No active borrowing found for this book")
    borrowing.returned_at = datetime.utcnow()
    book = next((b for b in books_db if b.id == book_id), None)
    if book:
        book.available += 1
    return borrowing

@app.get("/users/{user_id}/history", response_model=List[Borrowing])
def borrowing_history(user_id: str, current_user: User = Depends(get_current_user)):
    if current_user.id != user_id and current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    return [b for b in borrowings_db if b.user_id == user_id]

# Event Routes
@app.post("/events", response_model=Event)
def create_event(event: Event, current_user: User = Depends(get_current_user)):
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    events_db.append(event)
    return event

@app.get("/events", response_model=List[Event])
def get_events():
    return events_db

@app.post("/events/{event_id}/register")
def register_event(event_id: str, current_user: User = Depends(get_current_user)):
    event = next((e for e in events_db if e.id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if current_user.id in event.attendees:
        raise HTTPException(status_code=400, detail="Already registered")
    event.attendees.append(current_user.id)
    return event

@app.delete("/events/{event_id}/register")
def cancel_event_registration(event_id: str, current_user: User = Depends(get_current_user)):
    event = next((e for e in events_db if e.id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if current_user.id not in event.attendees:
        raise HTTPException(status_code=400, detail="Not registered for this event")
    event.attendees.remove(current_user.id)
    return {"message": "Registration canceled"}

@app.patch("/events/{event_id}", response_model=Event)
def update_event(event_id: str, event: Event, current_user: User = Depends(get_current_user)):
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    existing_event = next((e for e in events_db if e.id == event_id), None)
    if not existing_event:
        raise HTTPException(status_code=404, detail="Event not found")
    existing_event.title = event.title or existing_event.title
    existing_event.description = event.description or existing_event.description
    existing_event.date = event.date or existing_event.date
    existing_event.time = event.time or existing_event.time
    existing_event.location = event.location or existing_event.location
    return existing_event

@app.delete("/events/{event_id}")
def delete_event(event_id: str, current_user: User = Depends(get_current_user)):
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    global events_db
    events_db = [e for e in events_db if e.id != event_id]
    return {"message": "Event deleted"}

# Additional Routes
@app.post("/books/{book_id}/reserve")
def reserve_book(book_id: str, current_user: User = Depends(get_current_user)):
    book = next((b for b in books_db if b.id == book_id), None)
    if not book or book.available > 0:
        raise HTTPException(status_code=400, detail="Book is currently available or does not exist")
    if any(r["book_id"] == book_id and r["user_id"] == current_user.id for r in reservations_db):
        raise HTTPException(status_code=400, detail="Already reserved")
    reservation = {"book_id": book_id, "user_id": current_user.id, "reserved_at": datetime.utcnow()}
    reservations_db.append(reservation)
    return reservation

@app.delete("/books/{book_id}/reserve")
def cancel_reservation(book_id: str, current_user: User = Depends(get_current_user)):
    global reservations_db
    reservations_db = [r for r in reservations_db if not (r["book_id"] == book_id and r["user_id"] == current_user.id)]
    return {"message": "Reservation canceled"}
