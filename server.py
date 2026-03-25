import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from chatbot import graph

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory session storage: session_id -> graph state
sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str | None = None
    message: str
    products: list[dict] | None = None


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")


@app.get("/start")
def start_session():
    session_id = uuid.uuid4().hex
    result = graph.invoke({
        "conversation": [],
        "user_message": "Hi, I need help picking a product.",
        "assistant_message": None,
        "user_preferences": None,
        "recommended_products": None,
    })
    sessions[session_id] = result
    return ChatResponse(session_id=session_id, message=result["assistant_message"])


@app.post("/chat")
def chat(req: ChatRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    prev_state = sessions[req.session_id]
    result = graph.invoke({**prev_state, "user_message": req.message})

    if result["user_preferences"]:
        products = result["recommended_products"].to_dict(orient="records")
        del sessions[req.session_id]
        return ChatResponse(message="Great, I've found the best products for you!", products=products)

    sessions[req.session_id] = result
    return ChatResponse(message=result["assistant_message"])
