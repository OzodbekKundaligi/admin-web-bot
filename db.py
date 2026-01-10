import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
import logging
from bson import ObjectId

logging.basicConfig(level=logging.INFO)

# MongoDB ulanish
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://mongo:qJwpnbIGiqXcvjGhsMOhyPWJHzpmmnbV@shortline.proxy.rlwy.net:39174')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'garajhub')

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
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
        db[USERS_COLLECTION].create_index('category')
        
        # Startups collection
        db[STARTUPS_COLLECTION].create_index('owner_id')
        db[STARTUPS_COLLECTION].create_index('status')
        db[STARTUPS_COLLECTION].create_index('category')
        db[STARTUPS_COLLECTION].create_index([('status', ASCENDING), ('created_at', DESCENDING)])
        db[STARTUPS_COLLECTION].create_index([('category', ASCENDING), ('status', ASCENDING)])
        
        # Startup members collection
        db[STARTUP_MEMBERS_COLLECTION].create_index([('startup_id', ASCENDING), ('user_id', ASCENDING)], unique=True)
        db[STARTUP_MEMBERS_COLLECTION].create_index('startup_id')
        db[STARTUP_MEMBERS_COLLECTION].create_index('user_id')
        db[STARTUP_MEMBERS_COLLECTION].create_index([('startup_id', ASCENDING), ('status', ASCENDING)])
        
        logging.info("✅ MongoDB database initialized with indexes")
    except Exception as e:
        logging.error(f"❌ Database initialization error: {e}")

# =========== USERS FUNCTIONS ===========

def get_user(user_id: int) -> Optional[Dict]:
    """Foydalanuvchini ID bo'yicha olish"""
    try:
        user = db[USERS_COLLECTION].find_one({'user_id': user_id})
        if user:
            if '_id' in user:
                user['_id'] = str(user['_id'])
        return user
    except Exception as e:
        logging.error(f"Error getting user {user_id}: {e}")
        return None

def save_user(user_id: int, username: str, first_name: str, last_name: str = "", phone: str = "", 
              gender: str = "", birth_date: str = "", specialization: str = "", 
              experience: str = "", bio: str = ""):
    """Yangi foydalanuvchi qo'shish yoki mavjudni yangilash"""
    try:
        db[USERS_COLLECTION].update_one(
            {'user_id': user_id},
            {'$set': {
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
                'gender': gender,
                'birth_date': birth_date,
                'specialization': specialization,
                'experience': experience,
                'bio': bio,
                'joined_at': datetime.now()
            }},
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"Error saving user {user_id}: {e}")
        return False

def update_user_field(user_id: int, field: str, value: str):
    """Foydalanuvchi maydonini yangilash"""
    try:
        db[USERS_COLLECTION].update_one(
            {'user_id': user_id},
            {'$set': {field: value}}
        )
        return True
    except Exception as e:
        logging.error(f"Error updating user field {user_id}.{field}: {e}")
        return False

def update_user_specialization(user_id: int, specialization: str):
    """Foydalanuvchi mutaxassisligini yangilash"""
    try:
        db[USERS_COLLECTION].update_one(
            {'user_id': user_id},
            {'$set': {'specialization': specialization}}
        )
        return True
    except Exception as e:
        logging.error(f"Error updating user specialization {user_id}: {e}")
        return False

def update_user_experience(user_id: int, experience: str):
    """Foydalanuvchi tajribasini yangilash"""
    try:
        db[USERS_COLLECTION].update_one(
            {'user_id': user_id},
            {'$set': {'experience': experience}}
        )
        return True
    except Exception as e:
        logging.error(f"Error updating user experience {user_id}: {e}")
        return False

def get_user_joined_startups(user_id: int) -> List[str]:
    """Foydalanuvchi qo'shilgan startup ID larini olish"""
    try:
        members = db[STARTUP_MEMBERS_COLLECTION].find(
            {'user_id': user_id, 'status': 'accepted'},
            {'startup_id': 1}
        )
        return [member['startup_id'] for member in members]
    except Exception as e:
        logging.error(f"Error getting user joined startups {user_id}: {e}")
        return []

def get_startups_by_ids(startup_ids: List[str]) -> List[Dict]:
    """Bir nechta startup ID lar bo'yicha olish"""
    try:
        object_ids = []
        for startup_id in startup_ids:
            if ObjectId.is_valid(startup_id):
                object_ids.append(ObjectId(startup_id))
        
        if not object_ids:
            return []
            
        startups = list(db[STARTUPS_COLLECTION].find(
            {'_id': {'$in': object_ids}}
        ).sort('created_at', DESCENDING))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
        
        return startups
    except Exception as e:
        logging.error(f"Error getting startups by IDs: {e}")
        return []

def get_all_users() -> List[Dict]:
    """Barcha foydalanuvchilarni olish"""
    try:
        users = list(db[USERS_COLLECTION].find().sort('joined_at', DESCENDING))
        for user in users:
            if '_id' in user:
                user['_id'] = str(user['_id'])
            if 'joined_at' in user and isinstance(user['joined_at'], datetime):
                user['joined_at'] = user['joined_at'].strftime('%Y-%m-%d %H:%M:%S')
        return users
    except Exception as e:
        logging.error(f"Error getting all users: {e}")
        return []

def get_recent_users(limit: int = 10) -> List[Dict]:
    """So'nggi foydalanuvchilar"""
    try:
        users = list(db[USERS_COLLECTION].find(
            {}, 
            {'_id': 0, 'user_id': 1, 'username': 1, 'first_name': 1, 'last_name': 1, 
             'phone': 1, 'joined_at': 1, 'specialization': 1, 'experience': 1}
        ).sort('joined_at', DESCENDING).limit(limit))
        
        for user in users:
            if 'joined_at' in user and isinstance(user['joined_at'], datetime):
                user['joined_at'] = user['joined_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return users
    except Exception as e:
        logging.error(f"Error getting recent users: {e}")
        return []

# =========== STARTUPS FUNCTIONS ===========

def create_startup(name: str, description: str, logo: Optional[str], group_link: str, 
                   owner_id: int, required_skills: str = None, category: str = None, 
                   max_members: int = 10) -> str:
    """Yangi startup yaratish"""
    try:
        startup_data = {
            'name': name,
            'description': description,
            'logo': logo,
            'group_link': group_link,
            'owner_id': owner_id,
            'required_skills': required_skills or "",
            'category': category or "Boshqa",
            'max_members': max_members,
            'status': 'pending',
            'created_at': datetime.now(),
            'started_at': None,
            'ended_at': None,
            'results': ""
        }
        
        result = db[STARTUPS_COLLECTION].insert_one(startup_data)
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error creating startup: {e}")
        return None

def get_startup(startup_id: str) -> Optional[Dict]:
    """Startupni ID bo'yicha olish"""
    try:
        if not ObjectId.is_valid(startup_id):
            return None
            
        startup = db[STARTUPS_COLLECTION].find_one({'_id': ObjectId(startup_id)})
        if startup:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
            for date_field in ['created_at', 'started_at', 'ended_at']:
                if date_field in startup and isinstance(startup[date_field], datetime):
                    startup[date_field] = startup[date_field].strftime('%Y-%m-%d %H:%M:%S')
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
            for date_field in ['created_at', 'started_at', 'ended_at']:
                if date_field in startup and isinstance(startup[date_field], datetime):
                    startup[date_field] = startup[date_field].strftime('%Y-%m-%d %H:%M:%S')
        
        return startups
    except Exception as e:
        logging.error(f"Error getting startups for owner {owner_id}: {e}")
        return []

def get_startups_by_category(category: str) -> List[Dict]:
    """Kategoriya bo'yicha startuplarni olish"""
    try:
        startups = list(db[STARTUPS_COLLECTION].find(
            {'category': category}
        ).sort('created_at', DESCENDING))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
            for date_field in ['created_at', 'started_at', 'ended_at']:
                if date_field in startup and isinstance(startup[date_field], datetime):
                    startup[date_field] = startup[date_field].strftime('%Y-%m-%d %H:%M:%S')
        
        return startups
    except Exception as e:
        logging.error(f"Error getting startups by category {category}: {e}")
        return []

def get_all_categories() -> List[str]:
    """Barcha kategoriyalarni olish"""
    try:
        categories = db[STARTUPS_COLLECTION].distinct('category')
        return [cat for cat in categories if cat]
    except Exception as e:
        logging.error(f"Error getting all categories: {e}")
        return []

def get_pending_startups(page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
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
            if 'created_at' in startup and isinstance(startup['created_at'], datetime):
                startup['created_at'] = startup['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
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
            for date_field in ['created_at', 'started_at']:
                if date_field in startup and isinstance(startup[date_field], datetime):
                    startup[date_field] = startup[date_field].strftime('%Y-%m-%d %H:%M:%S')
        
        return startups, total
    except Exception as e:
        logging.error(f"Error getting active startups: {e}")
        return [], 0

def get_completed_startups(page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
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
            for date_field in ['created_at', 'started_at', 'ended_at']:
                if date_field in startup and isinstance(startup[date_field], datetime):
                    startup[date_field] = startup[date_field].strftime('%Y-%m-%d %H:%M:%S')
        
        return startups, total
    except Exception as e:
        logging.error(f"Error getting completed startups: {e}")
        return [], 0

def get_rejected_startups(page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
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
            if 'created_at' in startup and isinstance(startup['created_at'], datetime):
                startup['created_at'] = startup['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return startups, total
    except Exception as e:
        logging.error(f"Error getting rejected startups: {e}")
        return [], 0

def update_startup_status(startup_id: str, status: str):
    """Startup holatini yangilash"""
    try:
        if not ObjectId.is_valid(startup_id):
            return False
            
        update_data = {'status': status}
        
        if status == 'active':
            update_data['started_at'] = datetime.now()
        elif status in ['completed', 'rejected']:
            update_data['ended_at'] = datetime.now()
        
        result = db[STARTUPS_COLLECTION].update_one(
            {'_id': ObjectId(startup_id)},
            {'$set': update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating startup status {startup_id}: {e}")
        return False

def update_startup_results(startup_id: str, results: str, ended_at: datetime = None):
    """Startup natijalarini yangilash"""
    try:
        if not ObjectId.is_valid(startup_id):
            return False
            
        update_data = {'results': results}
        if ended_at:
            update_data['ended_at'] = ended_at
        else:
            update_data['ended_at'] = datetime.now()
        
        result = db[STARTUPS_COLLECTION].update_one(
            {'_id': ObjectId(startup_id)},
            {'$set': update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating startup results {startup_id}: {e}")
        return False

def get_recent_startups(limit: int = 10) -> List[Dict]:
    """So'nggi startuplar"""
    try:
        startups = list(db[STARTUPS_COLLECTION].find(
            {},
            {'name': 1, 'status': 1, 'created_at': 1, 'category': 1, 'owner_id': 1}
        ).sort('created_at', DESCENDING).limit(limit))
        
        for startup in startups:
            if '_id' in startup:
                startup['_id'] = str(startup['_id'])
            if 'created_at' in startup and isinstance(startup['created_at'], datetime):
                startup['created_at'] = startup['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return startups
    except Exception as e:
        logging.error(f"Error getting recent startups: {e}")
        return []

# =========== STARTUP MEMBERS FUNCTIONS ===========

def add_startup_member(startup_id: str, user_id: int, status: str = 'pending'):
    """Startupga a'zo qo'shish"""
    try:
        # Check if already exists
        existing = db[STARTUP_MEMBERS_COLLECTION].find_one({
            'startup_id': startup_id,
            'user_id': user_id
        })
        
        if existing:
            # Update status if exists
            db[STARTUP_MEMBERS_COLLECTION].update_one(
                {'_id': existing['_id']},
                {'$set': {'status': status}}
            )
            return str(existing['_id'])
        
        member_data = {
            'startup_id': startup_id,
            'user_id': user_id,
            'status': status,
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
        if not ObjectId.is_valid(request_id):
            return False
            
        result = db[STARTUP_MEMBERS_COLLECTION].update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'status': status}}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating join request {request_id}: {e}")
        return False

def get_startup_members(startup_id: str, page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
    """Startup a'zolarini olish"""
    try:
        skip = (page - 1) * per_page
        
        # Count total members
        total = db[STARTUP_MEMBERS_COLLECTION].count_documents({
            'startup_id': startup_id,
            'status': 'accepted'
        })
        
        # Get members with pagination
        members_cursor = db[STARTUP_MEMBERS_COLLECTION].find(
            {'startup_id': startup_id, 'status': 'accepted'}
        ).skip(skip).limit(per_page)
        
        members = list(members_cursor)
        
        # Format results
        formatted_members = []
        for member in members:
            user = get_user(member.get('user_id'))
            if user:
                formatted_members.append({
                    'user_id': user.get('user_id'),
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'username': user.get('username', ''),
                    'phone': user.get('phone', ''),
                    'specialization': user.get('specialization', ''),
                    'experience': user.get('experience', ''),
                    'bio': user.get('bio', '')
                })
        
        return formatted_members, total
    except Exception as e:
        logging.error(f"Error getting startup members {startup_id}: {e}")
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

def get_join_requests(startup_id: str) -> List[Dict]:
    """Startup uchun join requestlarni olish"""
    try:
        requests = list(db[STARTUP_MEMBERS_COLLECTION].find(
            {
                'startup_id': startup_id,
                'status': {'$in': ['pending', 'requested']}
            }
        ).sort('joined_at', DESCENDING))
        
        formatted_requests = []
        for req in requests:
            if '_id' in req:
                req['_id'] = str(req['_id'])
            if 'joined_at' in req and isinstance(req['joined_at'], datetime):
                req['joined_at'] = req['joined_at'].strftime('%Y-%m-%d %H:%M:%S')
            formatted_requests.append(req)
        
        return formatted_requests
    except Exception as e:
        logging.error(f"Error getting join requests for startup {startup_id}: {e}")
        return []

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
        return {
            'total_users': 0,
            'total_startups': 0,
            'active_startups': 0,
            'pending_startups': 0,
            'completed_startups': 0,
            'rejected_startups': 0
        }

# =========== DATABASE CONNECTION CHECK ===========

def check_database_connection() -> bool:
    """Database ulanishini tekshirish"""
    try:
        # Ping the database
        client.admin.command('ping')
        logging.info("✅ Database connection successful")
        return True
    except Exception as e:
        logging.error(f"❌ Database connection failed: {e}")
        return False

# =========== INITIALIZE DATABASE ===========

if __name__ == "__main__":
    print("Initializing database...")
    if check_database_connection():
        init_db()
        print("✅ Database initialized successfully")
    else:
        print("❌ Database connection failed")
