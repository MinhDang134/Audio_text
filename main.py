from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from audio.router import router
load_dotenv()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse,name="index_id")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
@app.get("/trangchu", response_class=HTMLResponse,name="trangchu_id")
async def read_root(request: Request):
    return templates.TemplateResponse("trangchu.html", {"request": request})
@app.get("/chatbox", response_class=HTMLResponse,name="chatbot_id")
async def read_root(request: Request):
    return templates.TemplateResponse("chatbox.html", {"request": request})
@app.get("/audio", response_class=HTMLResponse,name="audio_id")
async def read_root(request: Request):
    return templates.TemplateResponse("audio.html", {"request": request})

app.include_router(router)


