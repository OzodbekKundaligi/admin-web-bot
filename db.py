import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
import logging
from bson import ObjectId

logging.basicConfig(level=logging.INFO)

# MongoDB ulanish
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'garajhub')

client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

# Collection nomlari
USERS_COLLECTION = 'users'
STARTUPS_COLLECTION = 'startups'
STARTUP_MEMBERS_COLLECTION = 'startup_members'

# Indexlar yaratish
def init_db():
    try:
        # Users collection
        db[USERS_COLLECTION].create_index('user_id', unique=True)
        db[USERS_COLLECTION].create_index('username')
        db[USERS_COLLECTION].create_index('joined_at')
        
        # Startups collection
        db[STARTUPS_COLLECTION].create_index('owner_id')
        db[STARTUPS_COLLECTION].create_index('status')
        db[STARTUPS_COLLECTION].create_index([('status', ASCENDING), ('created_at', DESCENDING)])
        
        # Startup members collection
        db[STARTUP_MEMBERS_COLLECTION].create_index([('startup_id', ASCENDING), ('user_id', ASCENDING)], unique=True)
        db[STARTUP_MEMBERS_COLLECTION].create_index('startup_id')
        db[STARTUP_MEMBERS_COLLECTION].create_index('user_id')
        db[STARTUP_MEMBERS_COLLECTION].create_index([('startup_id', ASCENDING), ('status', ASCENDING)])
        
        logging.info("MongoDB database initialized with indexes")
    except Exception as e:
        logging.error(f"Database initialization error: {e}")

# =========== USERS FUNCTIONS ===========

def get_user(user_id: int) -> Optional[Dict]:
    """Foydalanuvchini ID bo'yicha olish"""
    try:
        user = db[USERS_COLLECTION].find_one({'user_id': user_id})
        if user and '_id' in user:
            user['_id'] = str(user['_id'])
        return user
    except Exception as e:
        logging.error(f"Error getting user {user_id}: {e}")
        return None

def save_user(user_id: int, username: str, first_name: str):
    """Yangi foydalanuvchi qo'shish yoki mavjudni yangilash"""
    try:
        db[USERS_COLLECTION].update_one(
            {'user_id': user_id},
            {'$set': {
                'username': username,
                'first_name': first_name,
                'joined_at': datetime.now()
            }},
            upsert=True
        )
    except Exception as e:
        logging.error(f"Error saving user {user_id}: {e}")

def update_user_field(user_id: int, field: str, value: str):
    """Foydalanuvchi maydonini yangilash"""
    try:
        db[USERS_COLLECTION].update_one(
            {'user_id': user_id},
            {'$set': {field: value}}
        )
    except Exception as e:
        logging.error(f"Error updating user field {user_id}.{field}: {e}")

# =========== STARTUPS FUNCTIONS ===========

def create_startup(name: str, description: str, logo: str, group_link: str, owner_id: int) -> str:
    """Yangi startup yaratish"""
    try:
        startup_data = {
            'name': name,
            'description': description,
            'logo': logo,
            'group_link': group_link,
            'owner_id': owner_id,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        result = db[STARTUPS_COLLECTION].insert_one(startup_data)
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error creating startup: {e}")
        return None

def get_startup(startup_id: str) -> Optional[Dict]:
    """Startupni ID bo'yicha olish"""
    try:
        startup = db[STARTUPS_COLLECTION].find_one({'_id': ObjectId(startup_id)})
        if startup and '_id' in startup:
            startup['_id'] = str(startup['_id'])
            startup['startup_id'] = str(startup['_id'])  # Kompatibilik uchun
        return startup
    except Exception as e:
        logging.error(f"Error getting startup {startup_id}: {e}")
        return None

def get_startups_by_owner(owner_id: int) -> List[Dict]:
    """Muallif ID bo'yicha startuplarni olish"""
    try:
        startups = list(db[STARTUPS_COLLECTION].find(
            {'owner_id': owner_id}
        ).sort('created_at', DESCENDING))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
                startup['startup_id'] = str(startup['_id'])
        
        return startups
    except Exception as e:
        logging.error(f"Error getting startups for owner {owner_id}: {e}")
        return []

def get_pending_startups(page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    """Kutilayotgan startuplar"""
    try:
        skip = (page - 1) * per_page
        total = db[STARTUPS_COLLECTION].count_documents({'status': 'pending'})
        
        startups = list(db[STARTUPS_COLLECTION].find(
            {'status': 'pending'}
        ).sort('created_at', DESCENDING).skip(skip).limit(per_page))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
                startup['startup_id'] = str(startup['_id'])
        
        return startups, total
    except Exception as e:
        logging.error(f"Error getting pending startups: {e}")
        return [], 0

def get_active_startups(page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
    """Faol startuplar"""
    try:
        skip = (page - 1) * per_page
        total = db[STARTUPS_COLLECTION].count_documents({'status': 'active'})
        
        startups = list(db[STARTUPS_COLLECTION].find(
            {'status': 'active'}
        ).sort('created_at', DESCENDING).skip(skip).limit(per_page))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
                startup['startup_id'] = str(startup['_id'])
        
        return startups, total
    except Exception as e:
        logging.error(f"Error getting active startups: {e}")
        return [], 0

def update_startup_status(startup_id: str, status: str):
    """Startup holatini yangilash"""
    try:
        update_data = {'status': status}
        
        if status == 'active':
            update_data['started_at'] = datetime.now()
        elif status == 'completed':
            update_data['ended_at'] = datetime.now()
        
        db[STARTUPS_COLLECTION].update_one(
            {'_id': ObjectId(startup_id)},
            {'$set': update_data}
        )
    except Exception as e:
        logging.error(f"Error updating startup status {startup_id}: {e}")

def update_startup_results(startup_id: str, results: str, ended_at: datetime = None):
    """Startup natijalarini yangilash"""
    try:
        update_data = {'results': results}
        if ended_at:
            update_data['ended_at'] = ended_at
        
        db[STARTUPS_COLLECTION].update_one(
            {'_id': ObjectId(startup_id)},
            {'$set': update_data}
        )
    except Exception as e:
        logging.error(f"Error updating startup results {startup_id}: {e}")

# =========== STARTUP MEMBERS FUNCTIONS ===========

def add_startup_member(startup_id: str, user_id: int):
    """Startupga a'zo qo'shish"""
    try:
        # Check if already exists
        existing = db[STARTUP_MEMBERS_COLLECTION].find_one({
            'startup_id': startup_id,
            'user_id': user_id
        })
        
        if existing:
            return str(existing['_id'])
        
        member_data = {
            'startup_id': startup_id,
            'user_id': user_id,
            'status': 'pending',
            'joined_at': datetime.now()
        }
        
        result = db[STARTUP_MEMBERS_COLLECTION].insert_one(member_data)
        return str(result.inserted_id)
    except DuplicateKeyError:
        logging.warning(f"Duplicate member {user_id} for startup {startup_id}")
        return None
    except Exception as e:
        logging.error(f"Error adding startup member: {e}")
        return None

def get_join_request_id(startup_id: str, user_id: int) -> Optional[str]:
    """Qo'shilish so'rovi ID sini olish"""
    try:
        request = db[STARTUP_MEMBERS_COLLECTION].find_one({
            'startup_id': startup_id,
            'user_id': user_id
        })
        
        if request and '_id' in request:
            return str(request['_id'])
        return None
    except Exception as e:
        logging.error(f"Error getting join request: {e}")
        return None

def update_join_request(request_id: str, status: str):
    """Qo'shilish so'rovini yangilash"""
    try:
        db[STARTUP_MEMBERS_COLLECTION].update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'status': status}}
        )
    except Exception as e:
        logging.error(f"Error updating join request {request_id}: {e}")

def get_startup_members(startup_id: str, page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    """Startup a'zolarini olish"""
    try:
        skip = (page - 1) * per_page
        
        # Total count
        pipeline = [
            {'$match': {'startup_id': startup_id, 'status': 'accepted'}},
            {'$lookup': {
                'from': USERS_COLLECTION,
                'localField': 'user_id',
                'foreignField': 'user_id',
                'as': 'user_info'
            }},
            {'$unwind': '$user_info'},
            {'$count': 'total'}
        ]
        
        count_result = list(db[STARTUP_MEMBERS_COLLECTION].aggregate(pipeline))
        total = count_result[0]['total'] if count_result else 0
        
        # Get members
        pipeline = [
            {'$match': {'startup_id': startup_id, 'status': 'accepted'}},
            {'$lookup': {
                'from': USERS_COLLECTION,
                'localField': 'user_id',
                'foreignField': 'user_id',
                'as': 'user_info'
            }},
            {'$unwind': '$user_info'},
            {'$skip': skip},
            {'$limit': per_page}
        ]
        
        members = list(db[STARTUP_MEMBERS_COLLECTION].aggregate(pipeline))
        
        # Format results
        formatted_members = []
        for member in members:
            user_info = member.get('user_info', {})
            formatted_members.append({
                'user_id': user_info.get('user_id'),
                'first_name': user_info.get('first_name', ''),
                'last_name': user_info.get('last_name', ''),
                'username': user_info.get('username', ''),
                'phone': user_info.get('phone', ''),
                'bio': user_info.get('bio', '')
            })
        
        return formatted_members, total
    except Exception as e:
        logging.error(f"Error getting startup members {startup_id}: {e}")
        return [], 0

# =========== STATISTICS FUNCTIONS ===========

def get_statistics() -> Dict:
    """Umumiy statistika"""
    try:
        total_users = db[USERS_COLLECTION].count_documents({})
        total_startups = db[STARTUPS_COLLECTION].count_documents({})
        active_startups = db[STARTUPS_COLLECTION].count_documents({'status': 'active'})
        pending_startups = db[STARTUPS_COLLECTION].count_documents({'status': 'pending'})
        completed_startups = db[STARTUPS_COLLECTION].count_documents({'status': 'completed'})
        rejected_startups = db[STARTUPS_COLLECTION].count_documents({'status': 'rejected'})
        
        return {
            'total_users': total_users,
            'total_startups': total_startups,
            'active_startups': active_startups,
            'pending_startups': pending_startups,
            'completed_startups': completed_startups,
            'rejected_startups': rejected_startups
        }
    except Exception as e:
        logging.error(f"Error getting statistics: {e}")
        return {}

def get_all_users() -> List[int]:
    """Barcha foydalanuvchi ID larini olish"""
    try:
        users = db[USERS_COLLECTION].find({}, {'user_id': 1})
        return [user['user_id'] for user in users]
    except Exception as e:
        logging.error(f"Error getting all users: {e}")
        return []

def get_recent_users(limit: int = 10) -> List[Dict]:
    """So'nggi foydalanuvchilar"""
    try:
        users = list(db[USERS_COLLECTION].find(
            {}, 
            {'_id': 0, 'user_id': 1, 'username': 1, 'first_name': 1, 'last_name': 1, 'joined_at': 1}
        ).sort('joined_at', DESCENDING).limit(limit))
        
        for user in users:
            if 'joined_at' in user and isinstance(user['joined_at'], datetime):
                user['joined_at'] = user['joined_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return users
    except Exception as e:
        logging.error(f"Error getting recent users: {e}")
        return []

def get_recent_startups(limit: int = 10) -> List[Dict]:
    """So'nggi startuplar"""
    try:
        startups = list(db[STARTUPS_COLLECTION].find(
            {},
            {'name': 1, 'status': 1, 'created_at': 1}
        ).sort('created_at', DESCENDING).limit(limit))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
                startup['startup_id'] = str(startup['_id'])
            if 'created_at' in startup and isinstance(startup['created_at'], datetime):
                startup['created_at'] = startup['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return startups
    except Exception as e:
        logging.error(f"Error getting recent startups: {e}")
        return []

def get_completed_startups(page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    """Yakunlangan startuplar"""
    try:
        skip = (page - 1) * per_page
        total = db[STARTUPS_COLLECTION].count_documents({'status': 'completed'})
        
        startups = list(db[STARTUPS_COLLECTION].find(
            {'status': 'completed'}
        ).sort('created_at', DESCENDING).skip(skip).limit(per_page))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
                startup['startup_id'] = str(startup['_id'])
        
        return startups, total
    except Exception as e:
        logging.error(f"Error getting completed startups: {e}")
        return [], 0

def get_rejected_startups(page: int = 1, per_page: int = 5) -> Tuple[List[Dict], int]:
    """Rad etilgan startuplar"""
    try:
        skip = (page - 1) * per_page
        total = db[STARTUPS_COLLECTION].count_documents({'status': 'rejected'})
        
        startups = list(db[STARTUPS_COLLECTION].find(
            {'status': 'rejected'}
        ).sort('created_at', DESCENDING).skip(skip).limit(per_page))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
                startup['startup_id'] = str(startup['_id'])
        
        return startups, total
    except Exception as e:
        logging.error(f"Error getting rejected startups: {e}")
        return [], 0

def get_all_startup_members(startup_id: str) -> List[int]:
    """Startupning barcha a'zolari (faqat user_id lar)"""
    try:
        members = db[STARTUP_MEMBERS_COLLECTION].find(
            {'startup_id': startup_id, 'status': 'accepted'},
            {'user_id': 1}
        )
        return [member['user_id'] for member in members]
    except Exception as e:
        logging.error(f"Error getting all startup members {startup_id}: {e}")
        return []