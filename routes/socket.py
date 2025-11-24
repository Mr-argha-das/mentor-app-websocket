from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
from sqlalchemy.orm import Session
from db.database import get_db
from models.messages import Conversation, Message
from firebase_admin import credentials, messaging
import random
import string
from models.userModels import User
router = APIRouter()
import firebase_admin

cred = credentials.Certificate("./utils/mmp--mymarketplace-firebase-adminsdk-fbsvc-314a0c52e9.json")
firebase_admin.initialize_app(cred)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_private_message(self, sender_id: str, receiver_id: str, message: str, db: Session):
        msg = Message(sender_id=sender_id, receiver_id=receiver_id, message=message)
        db.add(msg)
        db.commit()
        db.refresh(msg)

        conversation = db.query(Conversation).filter(
            ((Conversation.user1_id == sender_id) & (Conversation.user2_id == receiver_id)) |
            ((Conversation.user1_id == receiver_id) & (Conversation.user2_id == sender_id))
        ).first()

        if not conversation:
            conversation = Conversation(user1_id=sender_id, user2_id=receiver_id, last_message_id=msg.id)
            db.add(conversation)
        else:
            conversation.last_message_id = msg.id

        db.commit()

        receiver_socket = self.active_connections.get(receiver_id)
        if receiver_socket:
            await receiver_socket.send_json({
                "id": generate_random_string(length=10),
                "sender_id": sender_id,
                "message": message
            })

def generate_random_string(length=10):
    characters = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

manager = ConnectionManager()


def send_notification(token: str, title: str, body: str, id: int, fullname: str):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,   # device FCM token
            data={
                "userid": str(id),     # int को string में convert किया
                "fullname": fullname
            }
        )

        response = messaging.send(message)
        print(f"✅ Notification sent successfully: {response}")
        return response

    except messaging.UnregisteredError:
        # अगर token invalid है तो DB से हटा सकते हो
        print(f"⚠️ Invalid FCM token for user {id}, token: {token}")
        return None

    except Exception as e:
        # बाकी errors catch कर लो, ताकि code crash ना हो
        print(f"❌ Error sending notification to user {id}: {e}")
        return None
    

@router.websocket("/chat/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    db: Session = next(get_db())  # direct db session
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            receiver_id = data.get("receiver_id")
            user = db.query(User).filter(User.id == receiver_id).first()
            message = data.get("message")

            if not receiver_id or not message:
                await websocket.send_json({"error": "Missing receiver_id or message"})
                continue

            # if(user.fcm_Token != None):
                
            #     send_notification(user.fcm_Token, user.full_name, message, user_id, user.full_name )

            await manager.send_private_message(user_id, receiver_id, message, db)
            

    except WebSocketDisconnect:
        manager.disconnect(user_id)
