from fastapi import FastAPI


app = FastAPI(
    title="SPECTRA API",
    description="Hardware Intelligence Platform",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "Welcome to SPECTRA API",
        "status": "online",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }