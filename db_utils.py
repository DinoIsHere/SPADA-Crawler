import os
from supabase import create_client, Client
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv('login.env')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    # Generate a key if it doesn't exist (you should save this in your secrets!)
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print(f"ATTENTION: Generated new ENCRYPTION_KEY: {ENCRYPTION_KEY}")
    print("Save this in your environment variables immediately!")

fernet = Fernet(ENCRYPTION_KEY.encode())

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def encrypt_password(password: str) -> str:
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()

def get_user_profile(user_id: str):
    response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    return response.data

def update_user_profile(user_id: str, data: dict):
    response = supabase.table("profiles").update(data).eq("id", user_id).execute()
    return response.data
