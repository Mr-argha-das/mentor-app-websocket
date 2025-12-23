from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
from sqlalchemy.orm import Session
from db.database import get_db, SessionLocal
from models.messages import Conversation, Message
from models.userModels import User
from firebase_admin import credentials
import firebase_admin
import random
import string

router = APIRouter()

# ---------------- FIREBASE INIT ---------------- #

cred = credentials.Certificate(
    "./utils/mmp--mymarketplace-firebase-adminsdk-fbsvc-314a0c52e9.json"
)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# ---------------- HELPERS ---------------- #

def generate_random_string(length=10):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def serialize_user(user: User):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "profile_pic": user.profile_pic,
        "user_type": user.user_type,
        "status": user.status,
    }

# ---------------- CONNECTION MANAGER ---------------- #

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.presence_connections: List[WebSocket] = []

    # ---------- CHAT SOCKET ---------- #

    async def connect(self, websocket: WebSocket, user_id: str):
        user_id = str(user_id).strip()

        if not user_id.isdigit():
            await websocket.close(code=1008)
            return

        if user_id in self.active_connections:
            await self.active_connections[user_id].close()

        await websocket.accept()
        self.active_connections[user_id] = websocket
        print("CONNECTED USERS:", self.active_connections.keys())

    def disconnect(self, user_id: str):
        self.active_connections.pop(str(user_id), None)
        print("DISCONNECTED:", user_id)

    # ---------- PRESENCE SOCKET ---------- #

    async def connect_presence(self, websocket: WebSocket):
        await websocket.accept()
        self.presence_connections.append(websocket)

    def disconnect_presence(self, websocket: WebSocket):
        if websocket in self.presence_connections:
            self.presence_connections.remove(websocket)

    # ---------- CONNECTED USERS (MENTORS ONLY) ---------- #

    async def _get_connected_mentor_users(self):
        db = SessionLocal()
        try:
            user_ids = [int(uid) for uid in self.active_connections.keys()]
            if not user_ids:
                return []

            return (
                db.query(User)
                .filter(
                    User.id.in_(user_ids),
                    User.user_type == "Mentor"
                )
                .all()
            )
        finally:
            db.close()

    async def broadcast_connected_users(self):
        users = await self._get_connected_mentor_users()

        data = {
            "type": "connected_users",
            "count": len(users),
            "users": [serialize_user(u) for u in users]
        }

        for ws in self.presence_connections:
            try:
                await ws.send_json(data)
            except:
                pass

    # ---------- PRIVATE MESSAGE ---------- #

    async def send_private_message(
        self,
        sender_id: str,
        receiver_id: str,
        message: str
    ):
        sender_id = str(sender_id)
        receiver_id = str(receiver_id)

        db = SessionLocal()
        try:
            # ✅ SAVE MESSAGE
            msg = Message(
                sender_id=sender_id,
                receiver_id=receiver_id,
                message=message
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)

            # ✅ CONVERSATION UPDATE
            conversation = db.query(Conversation).filter(
                ((Conversation.user1_id == sender_id) &
                 (Conversation.user2_id == receiver_id)) |
                ((Conversation.user1_id == receiver_id) &
                 (Conversation.user2_id == sender_id))
            ).first()

            if not conversation:
                conversation = Conversation(
                    user1_id=sender_id,
                    user2_id=receiver_id,
                    last_message_id=msg.id
                )
                db.add(conversation)
            else:
                conversation.last_message_id = msg.id

            db.commit()

        finally:
            db.close()

        # ✅ REALTIME SEND (SENDER + RECEIVER)
        payload = {
            "id": msg.id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "message": message
        }

        for uid in [sender_id, receiver_id]:
            ws = self.active_connections.get(uid)
            if ws:
                await ws.send_json(payload)

# ---------------- MANAGER INSTANCE ---------------- #

manager = ConnectionManager()

# ---------------- CHAT WEBSOCKET ---------------- #

@router.websocket("/chat/ws/user/{user_id}")
async def chat_socket(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    await manager.broadcast_connected_users()

    try:
        while True:
            data = await websocket.receive_json()

            receiver_id = data.get("receiver_id")
            message = data.get("message")

            if not receiver_id or not message:
                await websocket.send_json({"error": "Invalid payload"})
                continue

            await manager.send_private_message(
                sender_id=user_id,
                receiver_id=receiver_id,
                message=message
            )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast_connected_users()

# ---------------- PRESENCE WEBSOCKET ---------------- #

@router.websocket("/chat/ws/presence/connected-users")
async def connected_users_ws(websocket: WebSocket):
    await manager.connect_presence(websocket)
    await manager.broadcast_connected_users()

    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        manager.disconnect_presence(websocket)
 