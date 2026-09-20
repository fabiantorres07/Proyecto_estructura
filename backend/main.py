from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"mensaje": "Hola SismoLab"}

@app.get("/eventos/{evento_id}")
def obtener_evento(evento_id: int):
    return {"id_recibido": evento_id}