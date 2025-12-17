from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
from sqlalchemy.orm import Session
from db.database import get_db
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
firebase_admin.initialize_app(cred)

# ---------------- HELPERS ---------------- #

def generate_random_string(length=10):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def serialize_user(user: User, include_sensitive: bool = False):
    data = {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "profile_pic": user.profile_pic,
        "user_type": user.user_type,
        "student_id": user.student_id,
        "service_type": user.service_type,
        "description": user.description,
        "skills_id": user.skills_id,
        "total_experience": user.total_experience,
        "users_field": user.users_field,
        "language_known": user.language_known,
        "linkedin_user": user.linkedin_user,
        "dob": user.dob.isoformat() if user.dob else None,
        "gender": user.gender,
        "resume_upload": user.resume_upload,
        "status": user.status,
        "coins": user.coins,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }

    # ⚠️ Optional sensitive fields
    if include_sensitive:
        data.update({
            "device_token": user.device_token,
            "token": user.token,
            "password": user.password,  # ❌ avoid unless admin use
        })

    return data

# ---------------- CONNECTION MANAGER ---------------- #

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.presence_connections: List[WebSocket] = []

    # ---------- CHAT SOCKET ---------- #

    async def connect(self, websocket: WebSocket, user_id: str):
        # 🔐 allow only numeric IDs
        if not user_id.isdigit():
            await websocket.close()
            return

        if user_id in self.active_connections:
            await self.active_connections[user_id].close()

        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    # ---------- PRESENCE SOCKET ---------- #

    async def connect_presence(self, websocket: WebSocket):
        await websocket.accept()
        self.presence_connections.append(websocket)

    def disconnect_presence(self, websocket: WebSocket):
        if websocket in self.presence_connections:
            self.presence_connections.remove(websocket)

    # ---------- CONNECTED USERS (MENTORS ONLY) ---------- #

    async def _get_connected_mentor_users(self, db: Session):
        user_ids = [
            int(uid) for uid in self.active_connections.keys()
            if uid.isdigit()
        ]

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

    async def send_connected_users(self, websocket: WebSocket, db: Session):
        users = await self._get_connected_mentor_users(db)

        await websocket.send_json({
            "type": "connected_users",
            "count": len(users),
            "users": [serialize_user(u, include_sensitive=True) for u in users]
        })

    async def broadcast_connected_users(self, db: Session):
        users = await self._get_connected_mentor_users(db)

        data = {
            "type": "connected_users",
            "count": len(users),
            "users": [serialize_user(u, include_sensitive=True) for u in users]
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
        message: str,
        db: Session
    ):
        msg = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

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

        receiver_socket = self.active_connections.get(receiver_id)
        if receiver_socket:
            await receiver_socket.send_json({
                "id": generate_random_string(),
                "sender_id": sender_id,
                "message": message
            })

# ---------------- MANAGER INSTANCE ---------------- #

manager = ConnectionManager()

# ---------------- CHAT WEBSOCKET ---------------- #
# 🔥 ROUTE FIXED (no conflict now)

@router.websocket("/chat/ws/user/{user_id}")
async def chat_socket(websocket: WebSocket, user_id: str):
    db: Session = next(get_db())
    await manager.connect(websocket, user_id)

    await manager.broadcast_connected_users(db)

    try:
        while True:
            data = await websocket.receive_json()

            receiver_id = data.get("receiver_id")
            message = data.get("message")

            if not receiver_id or not message:
                await websocket.send_json({"error": "Invalid payload"})
                continue

            await manager.send_private_message(
                user_id, receiver_id, message, db
            )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast_connected_users(db)

# ---------------- PRESENCE WEBSOCKET ---------------- #
# 🔥 ROUTE FIXED (no conflict now)

@router.websocket("/chat/ws/presence/connected-users")
async def connected_users_ws(websocket: WebSocket):
    db: Session = next(get_db())
    await manager.connect_presence(websocket)

    await manager.send_connected_users(websocket, db)

    try:
        while True:
            await websocket.receive()
    except WebSocketDisconnect:
        manager.disconnect_presence(websocket)
