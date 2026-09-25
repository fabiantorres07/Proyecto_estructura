from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.zones import router as zones_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zones_router)

@app.get("/")
def read_root():
    return {"mensaje": "Hola SismoLab"}

@app.get("/eventos/{evento_id}")
def obtener_evento(evento_id: int):
    return {"id_recibido": evento_id}