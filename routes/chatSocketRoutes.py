from fastapi import HTTPException, APIRouter, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from models.messages import Conversation, Message
from models.userModels import User

router = APIRouter()

@router.get("/chats/inbox/{user_id}")
async def get_inbox(user_id: str, db: Session = Depends(get_db)):
    selfUser = db.query(User).get(int(user_id))
    conversations = db.query(Conversation).filter(
        (Conversation.user1_id == user_id) | (Conversation.user2_id == user_id)
    ).all()
    inbox_list = []

    if not conversations:
        return {"message": "Here is all Conversation", "inbox": inbox_list, "status": 200}

    
    for convo in conversations:
        last_message_text = ""
        other_user_id = ""
        if int(user_id) == convo.user1_id:
            other_user_id = convo.user2_id
            print("pass1")
        elif int(user_id) == convo.user2_id:
            print("pass2")
            other_user_id = convo.user1_id
        print("================================")
        print(f"user id: {other_user_id}")
        user = db.query(User).get(other_user_id)
        print(user)

        last_msg = db.query(Message).get(convo.last_message_id)
        if last_msg:
            if int(last_msg.sender_id) == int(user_id):
                # last_message_text = "seen just now" if last_msg.is_read else "Sent just now"
                last_message_text = "Message seen" if last_msg.is_read == True else "Message sent's"
            else:
                last_message_text = last_msg.message
        else:
            last_message_text = ""

        inbox_list.append({
            "conversation_id": convo.id,
            "other_user": {
                "_id": user.id,
                "name": user.full_name,
                "profilePick": user.profile_pic,
                "is_readed": last_msg.is_read if last_msg else False,
                "sender_you": True if last_msg and int(last_msg.sender_id) == int(user_id) else False
            },
            "last_message": last_message_text,
            "timestamp": last_msg.timestamp if last_msg else None
        })

    return {"@message": "Here is all Conversation", "@inbox": inbox_list,"@eged_user": selfUser, "@status": 200, }


@router.get("/chats/history/{user1}/{user2}")
async def get_chat_history(user1: str, user2: str, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(
        ((Message.sender_id == user1) & (Message.receiver_id == user2)) |
        ((Message.sender_id == user2) & (Message.receiver_id == user1))
    ).order_by(Message.timestamp.asc()).all()

    return {
        "message": "All chats",
        "chat": [
            {"sender": msg.sender_id, "message": msg.message, "timestamp": msg.timestamp}
            for msg in messages
        ],
        "status": 200
    }


@router.post("/chats/mark_seen/{conversation_id}/{user_id}")
async def mark_messages_as_seen(conversation_id: str, user_id: str, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).get(conversation_id)

    if not conversation or (int(user_id) not in [conversation.user1_id, conversation.user2_id]):
        raise HTTPException(status_code=403, detail="Not authorized to access this chat.")

    db.query(Message).filter(
        Message.receiver_id == user_id,
        Message.sender_id.in_([conversation.user1_id, conversation.user2_id]),
        Message.is_read == False
    ).update({"is_read": True})
    db.commit()

    last_msg = db.query(Message).get(conversation.last_message_id)
    if last_msg and last_msg.receiver_id == user_id:
        last_msg.is_read = True
        db.commit()

    return {"message": "Messages marked as seen", "status": 200}


@router.get("/customers")
def get_all_customers(db: Session = Depends(get_db)):
    customers = db.query(User).all()
    return customers