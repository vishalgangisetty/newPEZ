import bcrypt
from pymongo import MongoClient
from datetime import datetime
from utils.config import Config
from utils.utils import setup_logger

logger = setup_logger(__name__)

class AuthManager:
    def __init__(self):
        self.client = MongoClient(Config.MONGO_URI, **Config.get_tls_kwargs())
        self.db = self.client.get_database("prescription_db")
        self.users = self.db.users

    def register_user(self, username, password):
        if self.users.find_one({"username": username}):
            return False, "Username already exists."
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        self.users.insert_one({
            "username": username,
            "password_hash": hashed,
            "created_at": datetime.utcnow()
        })
        logger.info(f"Registered user: {username}")
        return True, "User registered successfully."

    def login_user(self, username, password):
        user = self.users.find_one({"username": username})
        if not user:
            return False, "Invalid username or password."
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            logger.info(f"User logged in: {username}")
            return True, "Login successful."
        else:
            return False, "Invalid username or password."
