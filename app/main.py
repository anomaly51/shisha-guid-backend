from fastapi import FastAPI

app = FastAPI(
    title="ShishaGuid API",
    description="Backend API for ShishaGuid",
    version="0.1.0"
)

@app.get("/")
async def root():
    return {"message": "Welcome to ShishaGuid API"}