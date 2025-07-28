import models  # Ensure all models are registered with SQLAlchemy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import generator, metadata

app = FastAPI(
    title="Prompt Generator API",
    version="0.1.0"
)

# Optional CORS if you're using a frontend
# Define allowed origins for CORS. This is more secure than allowing all origins ("*").
# Based on our previous conversations, these are good defaults.
origins = [
    "http://localhost:8080",  # For local React development
    "https://promptgenfrontendupdated.vercel.app", # For your deployed frontend on Vercel
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include your API routers.
# It's best practice to define the "/api" prefix within each router file
# itself, rather than here in main.py.
app.include_router(generator.router)
app.include_router(metadata.router)
