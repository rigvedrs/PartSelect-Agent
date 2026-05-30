from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()  # load .env once at process startup

app = FastAPI(title="PartSelect AI Chat Agent")


@app.get("/health")
def health():
    return {"ok": True}
