from fastapi import FastAPI

app = FastAPI(title="PartSelect AI Chat Agent")


@app.get("/health")
def health():
    return {"ok": True}
