from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId
from datetime import datetime
from typing import Any, Optional
from config.settings import get_settings
from core.logging import get_logger

logger = get_logger("db.mongodb")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect() -> None:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_db_name]
    await _ensure_indexes()
    logger.info("mongodb_connected", db=settings.mongodb_db_name)


async def disconnect() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("mongodb_disconnected")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not connected. Call connect() first.")
    return _db


def get_gridfs() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(get_db())


async def _ensure_indexes() -> None:
    db = get_db()
    await db.sessions.create_index([("session_id", ASCENDING)], unique=True)
    await db.sessions.create_index([("created_at", DESCENDING)])
    await db.candidates.create_index([("session_id", ASCENDING)])
    await db.calls.create_index([("call_sid", ASCENDING)], unique=True)
    await db.calls.create_index([("session_id", ASCENDING)])
    await db.metrics.create_index([("session_id", ASCENDING)])
    await db.metrics.create_index([("created_at", DESCENDING)])


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(session_id: str, thread_id: str, initial_state: dict) -> dict:
    doc = {
        "session_id": session_id,
        "thread_id": thread_id,
        "state_snapshot": initial_state,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await get_db().sessions.insert_one(doc)
    logger.info("session_created", session_id=session_id)
    return doc


async def get_session(session_id: str) -> Optional[dict]:
    doc = await get_db().sessions.find_one({"session_id": session_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def update_session(session_id: str, update: dict) -> None:
    await get_db().sessions.update_one(
        {"session_id": session_id},
        {"$set": {"state_snapshot": update, "updated_at": datetime.utcnow()}},
    )


# ── Candidates ────────────────────────────────────────────────────────────────

async def save_candidates(session_id: str, candidates: list[dict]) -> None:
    if not candidates:
        return
    docs = [{"session_id": session_id, "created_at": datetime.utcnow(), **c} for c in candidates]
    await get_db().candidates.insert_many(docs)
    logger.info("candidates_saved", session_id=session_id, count=len(docs))


async def get_candidates(session_id: str) -> list[dict]:
    cursor = get_db().candidates.find({"session_id": session_id})
    docs = await cursor.to_list(length=100)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


# ── Calls ─────────────────────────────────────────────────────────────────────

async def create_call_record(session_id: str, candidate_id: str, call_sid: str, phone: str) -> None:
    await get_db().calls.insert_one({
        "session_id": session_id,
        "candidate_id": candidate_id,
        "call_sid": call_sid,
        "phone": phone,
        "status": "initiated",
        "conversation": [],
        "screening_data": {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    logger.info("call_record_created", call_sid=call_sid, phone=phone)


async def get_call_record(call_sid: str) -> Optional[dict]:
    doc = await get_db().calls.find_one({"call_sid": call_sid})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def update_call_record(call_sid: str, update: dict) -> None:
    await get_db().calls.update_one(
        {"call_sid": call_sid},
        {"$set": {**update, "updated_at": datetime.utcnow()}},
    )


async def append_call_turn(call_sid: str, role: str, text: str) -> None:
    await get_db().calls.update_one(
        {"call_sid": call_sid},
        {
            "$push": {"conversation": {"role": role, "text": text, "ts": datetime.utcnow()}},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )


async def get_session_calls(session_id: str) -> list[dict]:
    cursor = get_db().calls.find({"session_id": session_id})
    docs = await cursor.to_list(length=200)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


# ── Metrics ───────────────────────────────────────────────────────────────────

async def save_metric(session_id: str, metric: dict) -> None:
    await get_db().metrics.insert_one({
        "session_id": session_id,
        "created_at": datetime.utcnow(),
        **metric,
    })


# ── File storage (GridFS) ─────────────────────────────────────────────────────

async def store_file(filename: str, content: bytes, metadata: dict | None = None) -> str:
    bucket = get_gridfs()
    file_id = await bucket.upload_from_stream(
        filename, content, metadata=metadata or {}
    )
    logger.info("file_stored", filename=filename, file_id=str(file_id))
    return str(file_id)


async def read_file(file_id: str) -> bytes:
    bucket = get_gridfs()
    stream = await bucket.open_download_stream(ObjectId(file_id))
    return await stream.read()
