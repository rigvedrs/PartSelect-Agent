from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, cart, session as session_router

load_dotenv()

app = FastAPI(title="PartSelect AI Chat Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(cart.router)
app.include_router(session_router.router)


@app.get("/health")
def health():
    return {"ok": True}
