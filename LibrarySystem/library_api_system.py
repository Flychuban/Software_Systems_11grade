from fastapi import FastAPI, HTTPException, Depends, Query, Path, Body
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel, OAuth2 as OAuth2Model

# Initialize the FastAPI app
app = FastAPI(
    title="Library Management System API",
    description="A comprehensive API for managing a library, including user management, books, events, borrowing, and reservations.",
    version="1.0.0",
    contact={
        "name": "Library API Support",
        "email": "support@libraryapi.com",
    },
)

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
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the user")
    username: str = Field(..., description="Username of the user")
    password: str = Field(..., description="Password of the user")
    email: str = Field(..., description="Email address of the user")
    full_name: Optional[str] = Field(None, description="Full name of the user")
    role: str = Field(..., description="Role of the user, either 'user' or 'librarian'")

class Book(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the book")
    title: str = Field(..., description="Title of the book")
    description: str = Field(..., description="Description of the book")
    author: str = Field(..., description="Author of the book")
    year: int = Field(..., description="Year of publication")
    isbn: str = Field(..., description="ISBN number of the book")
    quantity: int = Field(..., description="Total quantity of the book in the library")
    available: int = Field(..., description="Available copies of the book")

class Borrowing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the borrowing record")
    user_id: str = Field(..., description="ID of the user who borrowed the book")
    book_id: str = Field(..., description="ID of the borrowed book")
    borrowed_at: datetime = Field(..., description="Timestamp when the book was borrowed")
    due_date: datetime = Field(..., description="Due date for returning the book")
    returned_at: Optional[datetime] = Field(None, description="Timestamp when the book was returned, if applicable")

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the event")
    title: str = Field(..., description="Title of the event")
    description: str = Field(..., description="Description of the event")
    date: datetime = Field(..., description="Date of the event")
    time: str = Field(..., description="Time of the event")
    location: str = Field(..., description="Location of the event")
    attendees: List[str] = Field(default_factory=list, description="List of user IDs who have registered for the event")

# Dependency to get the current user
def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Mocked function to retrieve the current user based on the token.
    """
    user = next((u for u in users_db if u.username == token), None)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user

# Routes with detailed Swagger documentation
@app.post("/users/register", response_model=User, summary="Register a new user")
def register_user(user: User):
    """
    Register a new user in the system.
    - **username**: Unique username of the user
    - **password**: Password for the account
    - **email**: Email address
    - **role**: Role of the user (user or librarian)
    """
    if any(u.username == user.username for u in users_db):
        raise HTTPException(status_code=400, detail="Username already exists")
    users_db.append(user)
    return user

@app.post("/users/login", summary="Login a user and get an access token")
def login_user(username: str = Body(..., description="Username of the user"), password: str = Body(..., description="Password of the user")):
    """
    Authenticate a user and return an access token.
    - **username**: The username of the user
    - **password**: The password of the user
    """
    user = next((u for u in users_db if u.username == username and u.password == password), None)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    return {"access_token": user.username, "token_type": "bearer"}

@app.get("/books", response_model=List[Book], summary="Get a list of books")
def get_books(
    title: Optional[str] = Query(None, description="Filter books by title"),
    author: Optional[str] = Query(None, description="Filter books by author"),
    year: Optional[int] = Query(None, description="Filter books by publication year"),
    available: Optional[bool] = Query(None, description="Filter books by availability"),
):
    """
    Retrieve a list of books with optional filters.
    """
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

@app.post("/books/{book_id}/borrow", summary="Borrow a book")
def borrow_book(book_id: str = Path(..., description="ID of the book to borrow"), current_user: User = Depends(get_current_user)):
    """
    Borrow a book if available.
    """
    book = next((b for b in books_db if b.id == book_id), None)
    if not book or book.available <= 0:
        raise HTTPException(status_code=400, detail="Book not available")
    book.available -= 1
    borrowing = Borrowing(
        user_id=current_user.id,
        book_id=book_id,
        borrowed_at=datetime.utcnow(),
        due_date=datetime.utcnow() + timedelta(days=14)
    )
    borrowings_db.append(borrowing)
    return borrowing

@app.post("/books/{book_id}/return", summary="Return a borrowed book")
def return_book(book_id: str = Path(..., description="ID of the book to return"), current_user: User = Depends(get_current_user)):
    """
    Return a borrowed book.
    - The user must have an active borrowing for the specified book.
    """
    borrowing = next((b for b in borrowings_db if b.book_id == book_id and b.user_id == current_user.id and not b.returned_at), None)
    if not borrowing:
        raise HTTPException(status_code=400, detail="No active borrowing found for this book")
    borrowing.returned_at = datetime.utcnow()
    book = next((b for b in books_db if b.id == book_id), None)
    if book:
        book.available += 1
    return borrowing

@app.get("/users/{user_id}/history", response_model=List[Borrowing], summary="Get borrowing history for a user")
def borrowing_history(user_id: str = Path(..., description="ID of the user"), current_user: User = Depends(get_current_user)):
    """
    Retrieve the borrowing history of a specific user.
    - Accessible by the user or a librarian.
    """
    if current_user.id != user_id and current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    return [b for b in borrowings_db if b.user_id == user_id]

@app.post("/events", response_model=Event, summary="Create a new event")
def create_event(event: Event, current_user: User = Depends(get_current_user)):
    """
    Create a new event in the library.
    - Only librarians can create events.
    """
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    events_db.append(event)
    return event

@app.get("/events", response_model=List[Event], summary="Get a list of events")
def get_events():
    """
    Retrieve a list of all events in the library.
    """
    return events_db

@app.post("/events/{event_id}/register", summary="Register for an event")
def register_event(event_id: str = Path(..., description="ID of the event"), current_user: User = Depends(get_current_user)):
    """
    Register the current user for an event.
    - The event must exist.
    - The user must not already be registered.
    """
    event = next((e for e in events_db if e.id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if current_user.id in event.attendees:
        raise HTTPException(status_code=400, detail="Already registered")
    event.attendees.append(current_user.id)
    return event

@app.delete("/events/{event_id}/register", summary="Cancel registration for an event")
def cancel_event_registration(event_id: str = Path(..., description="ID of the event"), current_user: User = Depends(get_current_user)):
    """
    Cancel the user's registration for an event.
    - The user must be registered for the event.
    """
    event = next((e for e in events_db if e.id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if current_user.id not in event.attendees:
        raise HTTPException(status_code=400, detail="Not registered for this event")
    event.attendees.remove(current_user.id)
    return {"message": "Registration canceled"}

@app.patch("/events/{event_id}", response_model=Event, summary="Update an event")
def update_event(
    event_id: str = Path(..., description="ID of the event to update"),
    event: Event = Body(..., description="Updated event details"),
    current_user: User = Depends(get_current_user)
):
    """
    Update the details of an existing event.
    - Only librarians can update events.
    """
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

@app.delete("/events/{event_id}", summary="Delete an event")
def delete_event(event_id: str = Path(..., description="ID of the event to delete"), current_user: User = Depends(get_current_user)):
    """
    Delete an event from the library.
    - Only librarians can delete events.
    """
    if current_user.role != "librarian":
        raise HTTPException(status_code=403, detail="Not authorized")
    global events_db
    events_db = [e for e in events_db if e.id != event_id]
    return {"message": "Event deleted"}

@app.post("/books/{book_id}/reserve", summary="Reserve a book")
def reserve_book(book_id: str = Path(..., description="ID of the book to reserve"), current_user: User = Depends(get_current_user)):
    """
    Reserve a book that is currently unavailable.
    - The book must not already be reserved by the user.
    """
    book = next((b for b in books_db if b.id == book_id), None)
    if not book or book.available > 0:
        raise HTTPException(status_code=400, detail="Book is currently available or does not exist")
    if any(r["book_id"] == book_id and r["user_id"] == current_user.id for r in reservations_db):
        raise HTTPException(status_code=400, detail="Already reserved")
    reservation = {"book_id": book_id, "user_id": current_user.id, "reserved_at": datetime.utcnow()}
    reservations_db.append(reservation)
    return reservation

@app.delete("/books/{book_id}/reserve", summary="Cancel a book reservation")
def cancel_reservation(book_id: str = Path(..., description="ID of the book to cancel reservation"), current_user: User = Depends(get_current_user)):
    """
    Cancel a reservation for a book.
    - The reservation must exist for the user.
    """
    global reservations_db
    reservations_db = [r for r in reservations_db if not (r["book_id"] == book_id and r["user_id"] == current_user.id)]
    return {"message": "Reservation canceled"}