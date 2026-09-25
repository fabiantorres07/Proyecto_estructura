from fastapi import FastAPI
from app.api.zones import router as zones_router

app = FastAPI()

app.include_router(zones_router)

@app.get("/")
def read_root():
    return {"mensaje": "Hola SismoLab"}

@app.get("/eventos/{evento_id}")
def obtener_evento(evento_id: int):
    return {"id_recibido": evento_id}