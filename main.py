from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import Base, engine
from routes import chatSocketRoutes
from routes import socket

# Create tables if not exists
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Chat Application",
    description="Private Chat with REST APIs + WebSocket (MySQL + SQLAlchemy)",
    version="1.0.0"
)

# ✅ CORS enable (for frontend like React/Flutter etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include Routers
app.include_router(chatSocketRoutes.router, tags=["Chats"])
app.include_router(socket.router, tags=["WebSocket"])

# ✅ Swagger me WebSocket show karne ke liye
@app.on_event("startup")
def add_websocket_docs():
    if "paths" not in app.openapi():
        return
    app.openapi()["paths"]["/chat/ws/{user_id}"] = {
        "get": {
            "summary": "WebSocket: Private Chat",
            "description": """
                **Real-time WebSocket for Private Messaging**

                **How to Use:**  
                1️⃣ Connect: `ws://localhost:8000/chat/ws/{user_id}`  
                2️⃣ Send JSON: `{"receiver_id": "USER_ID", "message": "Hello"}`  
                3️⃣ Receive: `{"sender_id": "USER_ID", "message": "Hi!"}`  

                **Events:**  
                - `"message"` → new message from another user  
                - `"disconnect"` → user disconnected  
            """,
            "responses": {101: {"description": "Switching Protocols"}},
        }
    }

@app.get("/")
def root():
    return {"message": "🚀 Chat API with MySQL + WebSocket is running!"}
