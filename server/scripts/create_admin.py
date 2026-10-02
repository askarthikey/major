"""
Seed an admin account into MongoDB.

Admin accounts are NOT self-service (per spec §1.3).
Run this script once to create the default admin.

Usage:
    python -m scripts.create_admin
    python -m scripts.create_admin --email custom@admin.com --password secret --name "Admin"
"""

import asyncio
import argparse
import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings
from api.auth import hash_password


async def create_admin(name: str, email: str, password: str):
    """Create an admin user in MongoDB."""
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.db_name]

    # Check if admin already exists
    existing = await db["users"].find_one({"email": email})
    if existing:
        print(f"[!] Admin with email '{email}' already exists. Skipping.")
        client.close()
        return

    # Ensure unique index on email
    await db["users"].create_index("email", unique=True)

    user_doc = {
        "_id": str(uuid.uuid4()),
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
        "role": "admin",
        "bus_id": None,  # Admins don't represent a bus
        "created_at": datetime.now(timezone.utc),
    }

    await db["users"].insert_one(user_doc)
    print(f"[OK] Admin account created successfully!")
    print(f"   Name:  {name}")
    print(f"   Email: {email}")
    print(f"   Role:  admin")
    print(f"   ID:    {user_doc['_id']}")

    client.close()


def main():
    parser = argparse.ArgumentParser(description="Create an admin user for the P2P Trading System")
    parser.add_argument("--name", default="Apoorva Admin", help="Admin display name")
    parser.add_argument("--email", default="apoorvaadmin@email.com", help="Admin email")
    parser.add_argument("--password", default="apoorvaadmin", help="Admin password")
    args = parser.parse_args()

    asyncio.run(create_admin(args.name, args.email, args.password))


if __name__ == "__main__":
    main()
