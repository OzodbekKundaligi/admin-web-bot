import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, send_from_directory
from flask_cors import CORS
from functools import wraps
import threading
import time
from bson import ObjectId
import traceback
import sys

# psutil uchun - agar mavjud bo'lmasa, o'rniga fake
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil moduli topilmadi. Tizim monitoringi cheklangan rejimda ishlaydi.")

# Bot va Database importlarini aniq qilamiz
sys.path.append('.')  # Joriy papkaga qo'shamiz

# Database import
try:
    from db import (
        init_db,
        get_user, save_user, update_user_field,
        create_startup, get_startup, get_startups_by_owner,
        get_pending_startups, get_active_startups, update_startup_status,
        get_statistics, get_all_users, get_recent_users, get_recent_startups,
        get_completed_startups, get_rejected_startups,
        get_startups_by_category, get_all_categories,
        get_startup_members, get_all_startup_members,
        update_startup_results, update_join_request,
        get_user_joined_startups, get_join_requests,
        check_database_connection  # Bu funksiya db.py da bo'lishi kerak
    )
    DB_AVAILABLE = True
    print("✅ Database moduli muvaffaqiyatli yuklandi")
except ImportError as e:
    print(f"❌ Database import xatosi: {e}")
    print("❒ Iltimos, db.py faylini tekshiring")
    DB_AVAILABLE = False

# Bot import
try:
    from main import bot, BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME
    BOT_AVAILABLE = True
    print("✅ Bot moduli muvaffaqiyatli yuklandi")
except ImportError as e:
    print(f"❌ Bot import xatosi: {e}")
    print("❒ Iltimos, main.py faylini tekshiring")
    BOT_AVAILABLE = False

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'garajhub-admin-secret-key-2024')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

CORS(app)

# Logger sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('admin_panel.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Adminlar ro'yxati (haqiqiy adminlar)
ADMINS = {
    'admin': {
        'password': 'admin123',
        'full_name': 'Super Admin',
        'email': 'admin@garajhub.uz',
        'role': 'superadmin'
    },
    'moderator': {
        'password': 'moderator123',
        'full_name': 'Moderator',
        'email': 'moderator@garajhub.uz',
        'role': 'moderator'
    }
}

# Login talab qiluvchi decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return jsonify({'success': False, 'error': 'Kirish talab qilinadi'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Role based access control
def role_required(roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if session.get('admin_role') not in roles:
                return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Botni ishga tushirish funksiyasi
def start_bot():
    if BOT_AVAILABLE:
        try:
            print("🤖 Telegram bot ishga tushmoqda...")
            bot.remove_webhook()
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.error(f"Bot xatosi: {e}")
            print(f"Bot xatosi: {e}")
    else:
        print("⚠️ Bot mavjud emas yoki yuklanmadi")

# ==================== UTILITY FUNCTIONS ====================

def format_datetime(dt_str):
    """Datetime ni formatlash"""
    if not dt_str:
        return ""
    
    try:
        if isinstance(dt_str, datetime):
            return dt_str.strftime('%Y-%m-%d %H:%M')
        
        # Turli formatlarni qo'llab-quvvatlash
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M']:
            try:
                dt = datetime.strptime(dt_str, fmt)
                return dt.strftime('%Y-%m-%d %H:%M')
            except:
                continue
        
        return str(dt_str)[:16]  # Faqat dastlabki 16 belgi
    except:
        return str(dt_str)

def format_date_for_display(date_str):
    """Ko'rish uchun formatlash"""
    try:
        if not date_str:
            return ""
        
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        diff = now - dt
        
        if diff.days == 0:
            if diff.seconds < 60:
                return "Hozirgina"
            elif diff.seconds < 3600:
                return f"{diff.seconds // 60} daqiqa oldin"
            else:
                return f"{diff.seconds // 3600} soat oldin"
        elif diff.days == 1:
            return "Kecha"
        elif diff.days < 7:
            return f"{diff.days} kun oldin"
        else:
            return dt.strftime('%d.%m.%Y')
    except:
        return date_str

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Asosiy sahifa"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Admin login API"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username va password kiriting'}), 400
        
        # Adminni tekshirish
        admin = ADMINS.get(username)
        if admin and admin['password'] == password:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_role'] = admin['role']
            session['admin_name'] = admin['full_name']
            
            logger.info(f"Admin kirildi: {username}")
            return jsonify({
                'success': True,
                'user': {
                    'username': username,
                    'full_name': admin['full_name'],
                    'email': admin['email'],
                    'role': admin['role']
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Noto\'g\'ri login yoki parol'}), 401
    except Exception as e:
        logger.error(f"Login error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'Server xatosi'}), 500

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Logout API"""
    try:
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Logout error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check_auth')
def check_auth():
    """Auth tekshirish"""
    try:
        if 'admin_logged_in' in session:
            return jsonify({
                'authenticated': True,
                'success': True,
                'user': {
                    'username': session.get('admin_username'),
                    'full_name': session.get('admin_name'),
                    'role': session.get('admin_role')
                }
            })
        return jsonify({'authenticated': False, 'success': True})
    except Exception as e:
        logger.error(f"Check auth error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/statistics')
@login_required
def get_statistics_data():
    """Statistika ma'lumotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        stats = get_statistics()
        
        # Bugungi yangi foydalanuvchilar
        today = datetime.now().strftime('%Y-%m-%d')
        recent_users = get_recent_users(1000)
        new_today = 0
        for user in recent_users:
            if user.get('joined_at', '').startswith(today):
                new_today += 1
        
        # Aktif foydalanuvchilar (oxirgi 7 kun)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        active_users = 0
        for user in recent_users:
            if user.get('joined_at', '') >= week_ago:
                active_users += 1
        
        # Kategoriyalar statistikasi
        categories = get_all_categories()
        category_stats = {}
        if categories:
            for category in categories:
                startups_in_category = len(get_startups_by_category(category))
                category_stats[category] = startups_in_category
        
        # Trend ma'lumotlari
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        yesterday_users = 0
        for user in recent_users:
            if user.get('joined_at', '').startswith(yesterday_str):
                yesterday_users += 1
        
        user_trend = 0
        if yesterday_users > 0 and new_today > 0:
            user_trend = ((new_today - yesterday_users) / yesterday_users * 100)
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': stats.get('total_users', 0),
                'total_startups': stats.get('total_startups', 0),
                'active_startups': stats.get('active_startups', 0),
                'pending_startups': stats.get('pending_startups', 0),
                'completed_startups': stats.get('completed_startups', 0),
                'rejected_startups': stats.get('rejected_startups', 0),
                'new_today': new_today,
                'active_users': active_users,
                'categories': category_stats,
                'trends': {
                    'users': f"{user_trend:+.1f}%" if user_trend != 0 else "+0%",
                    'startups': "+0%"
                }
            }
        })
    except Exception as e:
        logger.error(f"Statistics error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/users')
@login_required
def get_users():
    """Foydalanuvchilar ro'yxati"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        
        # DB dan foydalanuvchilarni olish
        users = get_all_users()
        
        # Filtrlash
        if search:
            filtered_users = []
            for user in users:
                user_text = (
                    f"{user.get('first_name', '')} "
                    f"{user.get('last_name', '')} "
                    f"{user.get('username', '')} "
                    f"{user.get('phone', '')}"
                ).lower()
                if search.lower() in user_text:
                    filtered_users.append(user)
            users = filtered_users
        
        # Pagination
        total = len(users)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_users = users[start_idx:end_idx]
        
        # Formatlash
        formatted_users = []
        for user in paginated_users:
            # Qo'shilgan startaplar soni
            user_id = user.get('user_id')
            joined_startups = 0
            if user_id:
                try:
                    joined_startups = len(get_startups_by_owner(user_id))
                except:
                    pass
            
            formatted_users.append({
                'id': str(user_id) if user_id else '',
                'user_id': user_id,
                'first_name': user.get('first_name', 'Noma\'lum'),
                'last_name': user.get('last_name', ''),
                'username': f"@{user.get('username', '')}" if user.get('username') else '-',
                'phone': user.get('phone', 'Kiritilmagan'),
                'joined_at': format_date_for_display(user.get('joined_at', '')),
                'status': 'active',
                'startup_count': joined_startups,
                'specialization': user.get('specialization', 'Kiritilmagan'),
                'experience': user.get('experience', 'Kiritilmagan')
            })
        
        return jsonify({
            'success': True,
            'data': formatted_users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page if per_page > 0 else 1
            }
        })
    except Exception as e:
        logger.error(f"Users error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/users/<user_id>')
@login_required
def get_user_detail(user_id):
    """Foydalanuvchi tafsilotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        # User_id ni int ga o'tkazish
        try:
            user_id_int = int(user_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Noto\'g\'ri user ID'}), 400
        
        user = get_user(user_id_int)
        if not user:
            return jsonify({'success': False, 'error': 'Foydalanuvchi topilmadi'}), 404
        
        # User startaplari
        user_startups = get_startups_by_owner(user_id_int)
        startups_data = []
        for startup in user_startups[:10]:  # Faqat 10 tasini
            startups_data.append({
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', 'Noma\'lum'),
                'status': startup.get('status', 'unknown'),
                'created_at': format_datetime(startup.get('created_at', ''))
            })
        
        # Qo'shilgan startaplar
        joined_startups = get_user_joined_startups(user_id_int)
        
        return jsonify({
            'success': True,
            'data': {
                'id': user.get('user_id'),
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', ''),
                'username': user.get('username', ''),
                'phone': user.get('phone', ''),
                'gender': user.get('gender', ''),
                'birth_date': user.get('birth_date', ''),
                'specialization': user.get('specialization', ''),
                'experience': user.get('experience', ''),
                'bio': user.get('bio', ''),
                'joined_at': format_date_for_display(user.get('joined_at', '')),
                'startup_count': len(user_startups),
                'joined_startup_count': len(joined_startups),
                'startups': startups_data,
                'stats': {
                    'created': len(user_startups),
                    'joined': len(joined_startups),
                    'active': sum(1 for s in user_startups if s.get('status') == 'active'),
                    'completed': sum(1 for s in user_startups if s.get('status') == 'completed')
                }
            }
        })
    except Exception as e:
        logger.error(f"User detail error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startups')
@login_required
def get_startups_list():
    """Startaplar ro'yxati"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        status = request.args.get('status', 'all')
        category = request.args.get('category', 'all')
        
        # Barcha startaplarni yig'ish
        all_startups = []
        
        if status == 'all':
            # Barcha statusdagi startaplar
            active_startups, _ = get_active_startups(1, 1000)
            pending_startups, _ = get_pending_startups(1, 1000)
            completed_startups, _ = get_completed_startups(1, 1000)
            rejected_startups, _ = get_rejected_startups(1, 1000)
            all_startups = active_startups + pending_startups + completed_startups + rejected_startups
        elif status == 'active':
            all_startups, _ = get_active_startups(1, 1000)
        elif status == 'pending':
            all_startups, _ = get_pending_startups(1, 1000)
        elif status == 'completed':
            all_startups, _ = get_completed_startups(1, 1000)
        elif status == 'rejected':
            all_startups, _ = get_rejected_startups(1, 1000)
        
        # Kategoriya bo'yicha filtrlash
        if category != 'all':
            all_startups = [s for s in all_startups if s.get('category') == category]
        
        # Qidiruv bo'lsa
        if search:
            filtered = []
            for startup in all_startups:
                startup_name = startup.get('name', '').lower()
                startup_desc = startup.get('description', '').lower()
                search_term = search.lower()
                
                if (search_term in startup_name or 
                    search_term in startup_desc):
                    filtered.append(startup)
            all_startups = filtered
        
        # Sort by created_at desc
        all_startups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        total = len(all_startups)
        
        # Pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_startups = all_startups[start_idx:end_idx] if total > 0 else []
        
        # Formatlash
        formatted_startups = []
        for startup in paginated_startups:
            # Muallif ma'lumotlari
            owner_id = startup.get('owner_id')
            owner_name = "Noma'lum"
            if owner_id:
                owner = get_user(owner_id)
                if owner:
                    owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
                    if not owner_name:
                        owner_name = f"User {owner_id}"
            
            # A'zolar soni
            startup_id = str(startup.get('_id', ''))
            members_count = 0
            try:
                members_count = len(get_all_startup_members(startup_id))
            except:
                pass
            
            # Status matni
            status_texts = {
                'pending': '⏳ Kutilmoqda',
                'active': '▶️ Faol',
                'completed': '✅ Yakunlangan',
                'rejected': '❌ Rad etilgan'
            }
            
            description = startup.get('description', '')
            if len(description) > 100:
                description = description[:100] + '...'
            
            formatted_startups.append({
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', 'Noma\'lum'),
                'description': description,
                'owner_name': owner_name,
                'owner_id': owner_id,
                'status': startup.get('status', 'pending'),
                'status_text': status_texts.get(startup.get('status', 'pending'), startup.get('status', 'pending')),
                'category': startup.get('category', 'Boshqa'),
                'created_at': format_date_for_display(startup.get('created_at', '')),
                'started_at': format_date_for_display(startup.get('started_at', '')),
                'ended_at': format_date_for_display(startup.get('ended_at', '')),
                'member_count': members_count,
                'max_members': startup.get('max_members', 0),
                'logo': startup.get('logo', ''),
                'group_link': startup.get('group_link', '')
            })
        
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1
        
        return jsonify({
            'success': True,
            'data': formatted_startups,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages
            }
        })
    except Exception as e:
        logger.error(f"Startups error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/startup/<startup_id>', methods=['GET'])
@login_required
def get_startup_details(startup_id):
    """Startap tafsilotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        startup = get_startup(startup_id)
        if not startup:
            return jsonify({'success': False, 'error': 'Startap topilmadi'}), 404
        
        # Muallif ma'lumotlari
        owner_id = startup.get('owner_id')
        owner_info = None
        if owner_id:
            owner = get_user(owner_id)
            if owner:
                owner_info = {
                    'id': owner.get('user_id'),
                    'first_name': owner.get('first_name', ''),
                    'last_name': owner.get('last_name', ''),
                    'phone': owner.get('phone', ''),
                    'username': owner.get('username', ''),
                    'bio': owner.get('bio', '')
                }
        
        # A'zolar
        members = []
        try:
            members_data, _ = get_startup_members(startup_id, 1, 50)
            members = members_data
        except Exception as e:
            logger.error(f"Members olishda xato: {e}")
        
        # Status matni
        status_texts = {
            'pending': '⏳ Kutilmoqda',
            'active': '▶️ Faol',
            'completed': '✅ Yakunlangan',
            'rejected': '❌ Rad etilgan'
        }
        
        # Join requests
        join_requests = []
        try:
            join_requests = get_join_requests(startup_id)
        except Exception as e:
            logger.error(f"Join requests olishda xato: {e}")
        
        return jsonify({
            'success': True,
            'data': {
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', ''),
                'description': startup.get('description', ''),
                'status': startup.get('status', ''),
                'status_text': status_texts.get(startup.get('status'), startup.get('status')),
                'created_at': format_date_for_display(startup.get('created_at', '')),
                'started_at': format_date_for_display(startup.get('started_at', '')),
                'ended_at': format_date_for_display(startup.get('ended_at', '')),
                'results': startup.get('results', ''),
                'group_link': startup.get('group_link', ''),
                'logo': startup.get('logo', ''),
                'owner': owner_info,
                'members': members,
                'member_count': len(members),
                'max_members': startup.get('max_members', 0),
                'required_skills': startup.get('required_skills', ''),
                'category': startup.get('category', 'Boshqa'),
                'join_requests': join_requests
            }
        })
    except Exception as e:
        logger.error(f"Startup details error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startup/<startup_id>/approve', methods=['POST'])
@login_required
@role_required(['superadmin', 'moderator'])
def approve_startup(startup_id):
    """Startapni tasdiqlash"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        # Startup holatini yangilash
        success = update_startup_status(startup_id, 'active')
        
        if not success:
            return jsonify({'success': False, 'error': 'Startap holatini yangilashda xato'}), 500
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if startup and startup.get('owner_id'):
                    bot.send_message(
                        startup['owner_id'],
                        f"🎉 Tabriklaymiz! Sizning '{startup['name']}' startupingiz tasdiqlandi!\n\n"
                        f"Startup kanalda e'lon qilindi."
                    )
                    
                    # Kanalga post yuborish
                    try:
                        user = get_user(startup['owner_id'])
                        owner_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else "Noma'lum"
                        
                          channel_text = (
            f"🚀 <b>{startup['name']}</b>\n\n"
            f"📝 {startup['description']}\n\n"
            f"👤 <b>Muallif:</b> {owner_name}\n"
            f"🏷️ <b>Kategoriya:</b> {startup.get('category', '—')}\n"
            f"🔧 <b>Kerakli mutaxassislar:</b>\n{startup.get('required_skills', '—')}\n\n"
            f"👥 <b>A'zolar:</b> 0 / {startup.get('max_members', '—')}\n\n"
            f"👉 <b>Startupga qo'shilish uchun pastdagi tugmani bosing.</b>\n"
            f"➕ <b>O'z startupingizni yaratish uchun:</b> @{bot.get_me().username}"
        )
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🤝 Startupga qo\'shilish', callback_data=f'join_startup_{startup_id}'))
                        
                        if startup.get('logo'):
                            bot.send_photo(CHANNEL_USERNAME, startup['logo'], caption=channel_text, reply_markup=markup, parse_mode='HTML')
                        else:
                            bot.send_message(CHANNEL_USERNAME, channel_text, reply_markup=markup, parse_mode='HTML')
                    except Exception as e:
                        logger.error(f"Kanalga post yuborishda xato: {e}")
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
        
        logger.info(f"Startup approved: {startup_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Startap tasdiqlandi va kanalga joylandi'
        })
    except Exception as e:
        logger.error(f"Approve startup error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startup/<startup_id>/reject', methods=['POST'])
@login_required
@role_required(['superadmin', 'moderator'])
def reject_startup(startup_id):
    """Startapni rad etish"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        data = request.json
        reason = data.get('reason', 'Qoidalarga muvofiq emas')
        
        success = update_startup_status(startup_id, 'rejected')
        
        if not success:
            return jsonify({'success': False, 'error': 'Startap holatini yangilashda xato'}), 500
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if startup and startup.get('owner_id'):
                    bot.send_message(
                        startup['owner_id'],
                        f"❌ Sizning '{startup['name']}' startupingiz rad etildi.\n\n"
                        f"Sabab: {reason}\n\n"
                        f"Iltimos, qoidalarga muvofiq qayta yarating."
                    )
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
        
        logger.info(f"Startup rejected: {startup_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Startap rad etildi'
        })
    except Exception as e:
        logger.error(f"Reject startup error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startup/<startup_id>/complete', methods=['POST'])
@login_required
@role_required(['superadmin', 'moderator'])
def complete_startup(startup_id):
    """Startapni yakunlash (admin)"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        data = request.json
        results = data.get('results', 'Muvaffaqiyatli yakunlandi')
        
        # Startup holatini yangilash
        success_status = update_startup_status(startup_id, 'completed')
        success_results = update_startup_results(startup_id, results, datetime.now())
        
        if not success_status or not success_results:
            return jsonify({'success': False, 'error': 'Startap holatini yangilashda xato'}), 500
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if startup:
                    # Barcha a'zolarga xabar
                    members = get_all_startup_members(startup_id)
                    for member_id in members:
                        try:
                            bot.send_message(
                                member_id,
                                f"🏁 <b>Startup yakunlandi</b>\n\n"
                                f"🎯 <b>{startup['name']}</b>\n"
                                f"📅 <b>Yakunlangan sana:</b> {datetime.now().strftime('%d-%m-%Y')}\n"
                                f"📝 <b>Natijalar:</b>\n{results}"
                            )
                        except Exception as e:
                            logger.error(f"Memberga xabar yuborishda xato {member_id}: {e}")
                    
                    # Muallifga alohida xabar
                    if startup.get('owner_id'):
                        bot.send_message(
                            startup['owner_id'],
                            f"🎊 Tabriklaymiz! '{startup['name']}' startapingiz muvaffaqiyatli yakunlandi!\n\n"
                            f"Natijalar: {results}"
                        )
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
        
        logger.info(f"Startup completed: {startup_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Startap yakunlandi'
        })
    except Exception as e:
        logger.error(f"Complete startup error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/broadcast', methods=['POST'])
@login_required
@role_required(['superadmin'])
def broadcast_message():
    """Xabar yuborish"""
    try:
        data = request.json
        message = data.get('message')
        recipient_type = data.get('recipient_type', 'all')
        
        if not message:
            return jsonify({'success': False, 'error': 'Xabar matni kiritilmagan'}), 400
        
        # Bot orqali xabar yuborish
        sent_count = 0
        failed_count = 0
        
        if BOT_AVAILABLE and DB_AVAILABLE:
            try:
                users = get_all_users()
                
                for user in users:
                    try:
                        user_id = user.get('user_id')
                        if user_id:
                            bot.send_message(user_id, f"📢 <b>Yangilik!</b>\n\n{message}", parse_mode='HTML')
                            sent_count += 1
                            time.sleep(0.05)  # Flood dan qochish
                    except Exception as e:
                        logger.error(f"Foydalanuvchiga xabar yuborishda xato {user.get('user_id')}: {e}")
                        failed_count += 1
            except Exception as e:
                logger.error(f"Xabar yuborishda xato: {e}")
        
        logger.info(f"Broadcast message sent to {sent_count} users, failed: {failed_count}")
        
        return jsonify({
            'success': True,
            'message': 'Xabar yuborildi',
            'data': {
                'id': str(ObjectId()),
                'message': message[:100] + '...' if len(message) > 100 else message,
                'recipient_type': recipient_type,
                'sent_at': datetime.now().isoformat(),
                'sent_by': session.get('admin_username'),
                'stats': {
                    'sent': sent_count,
                    'failed': failed_count,
                    'total': sent_count + failed_count
                }
            }
        })
    except Exception as e:
        logger.error(f"Broadcast error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/user-growth')
@login_required
def get_user_growth():
    """Foydalanuvchi o'sishi uchun analytics"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        period = request.args.get('period', 'month')
        days = 30 if period == 'month' else 7 if period == 'week' else 30
        
        # Oxirgi N kun uchun ma'lumotlar
        dates = []
        new_users_data = []
        total_users_data = []
        
        users = get_recent_users(10000)
        
        # Har bir kun uchun hisoblash
        for i in range(days - 1, -1, -1):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            # Shu kungi yangi foydalanuvchilar
            new_users = 0
            total_users = 0
            
            for user in users:
                joined_at = user.get('joined_at', '')
                if isinstance(joined_at, str):
                    if joined_at.startswith(date_str):
                        new_users += 1
                    if joined_at <= date_str:
                        total_users += 1
            
            dates.append(date.strftime('%d.%m') if i % (max(1, days // 10)) == 0 else '')
            new_users_data.append(new_users)
            total_users_data.append(total_users)
        
        return jsonify({
            'success': True,
            'data': {
                'labels': dates,
                'datasets': [
                    {
                        'label': 'Yangi foydalanuvchilar',
                        'data': new_users_data,
                        'borderColor': '#000000',
                        'backgroundColor': 'rgba(0, 0, 0, 0.1)',
                        'tension': 0.4,
                        'fill': True
                    },
                    {
                        'label': 'Jami foydalanuvchilar',
                        'data': total_users_data,
                        'borderColor': '#666666',
                        'backgroundColor': 'transparent',
                        'tension': 0.4,
                        'hidden': True
                    }
                ]
            }
        })
    except Exception as e:
        logger.error(f"Analytics error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/startup-distribution')
@login_required
def get_startup_distribution():
    """Startap taqsimoti"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        stats = get_statistics()
        
        data = {
            'labels': ['Faol', 'Kutilayotgan', 'Yakunlangan', 'Rad etilgan'],
            'datasets': [{
                'data': [
                    stats.get('active_startups', 0),
                    stats.get('pending_startups', 0),
                    stats.get('completed_startups', 0),
                    stats.get('rejected_startups', 0)
                ],
                'backgroundColor': [
                    '#000000',
                    '#666666',
                    '#999999',
                    '#CCCCCC'
                ],
                'borderColor': '#ffffff',
                'borderWidth': 2
            }]
        }
        
        return jsonify({
            'success': True,
            'data': data,
            'total': stats.get('total_startups', 0)
        })
    except Exception as e:
        logger.error(f"Distribution error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories')
@login_required
def get_categories():
    """Barcha kategoriyalar"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        categories = get_all_categories()
        
        # Har bir kategoriya uchun statistikalar
        category_stats = []
        for category in categories:
            startups = get_startups_by_category(category)
            active_count = sum(1 for s in startups if s.get('status') == 'active')
            pending_count = sum(1 for s in startups if s.get('status') == 'pending')
            completed_count = sum(1 for s in startups if s.get('status') == 'completed')
            rejected_count = sum(1 for s in startups if s.get('status') == 'rejected')
            
            category_stats.append({
                'name': category,
                'total': len(startups),
                'active': active_count,
                'pending': pending_count,
                'completed': completed_count,
                'rejected': rejected_count
            })
        
        # Sort by total descending
        category_stats.sort(key=lambda x: x['total'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': category_stats
        })
    except Exception as e:
        logger.error(f"Categories error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
@role_required(['superadmin'])
def settings():
    """Sozlamalar"""
    try:
        if request.method == 'GET':
            # Sozlamalarni olish
            settings_data = {
                'site_name': 'GarajHub',
                'admin_email': 'admin@garajhub.uz',
                'timezone': 'Asia/Tashkent',
                'bot_token': BOT_TOKEN if BOT_AVAILABLE else 'Noma\'lum',
                'channel_username': CHANNEL_USERNAME if BOT_AVAILABLE else 'Noma\'lum',
                'admin_id': ADMIN_ID if BOT_AVAILABLE else 'Noma\'lum',
                'bot_status': 'online' if BOT_AVAILABLE else 'offline',
                'db_status': 'online' if DB_AVAILABLE else 'offline',
                'version': '1.0.0',
                'uptime': int(time.time())
            }
            
            return jsonify({
                'success': True,
                'data': settings_data
            })
        else:
            # Sozlamalarni yangilash
            data = request.json
            
            logger.info(f"Settings updated by {session.get('admin_username')}: {data}")
            
            return jsonify({
                'success': True, 
                'message': 'Sozlamalar saqlandi'
            })
    except Exception as e:
        logger.error(f"Settings error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/system/health')
@login_required
def system_health():
    """Tizim holati"""
    try:
        health_data = {
            'cpu': {
                'usage': 0,
                'cores': 1,
                'status': 'good'
            },
            'memory': {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0,
                'status': 'good'
            },
            'disk': {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0,
                'status': 'good'
            },
            'services': {
                'bot': 'online' if BOT_AVAILABLE else 'offline',
                'database': 'online' if DB_AVAILABLE else 'offline',
                'web_server': 'online'
            },
            'uptime': int(time.time()),
            'timestamp': datetime.now().isoformat()
        }
        
        if PSUTIL_AVAILABLE:
            # Haqiqiy ma'lumotlar
            try:
                memory = psutil.virtual_memory()
                cpu = psutil.cpu_percent(interval=1)
                disk = psutil.disk_usage('/')
                
                health_data.update({
                    'cpu': {
                        'usage': cpu,
                        'cores': psutil.cpu_count(),
                        'status': 'good' if cpu < 80 else 'warning' if cpu < 95 else 'critical'
                    },
                    'memory': {
                        'total': memory.total,
                        'used': memory.used,
                        'free': memory.free,
                        'percent': memory.percent,
                        'status': 'good' if memory.percent < 80 else 'warning' if memory.percent < 95 else 'critical'
                    },
                    'disk': {
                        'total': disk.total,
                        'used': disk.used,
                        'free': disk.free,
                        'percent': disk.percent,
                        'status': 'good' if disk.percent < 80 else 'warning' if disk.percent < 95 else 'critical'
                    }
                })
            except Exception as e:
                logger.error(f"System monitoring error: {e}")
        
        return jsonify({
            'success': True,
            'data': health_data
        })
    except Exception as e:
        logger.error(f"System health error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== NEW APIs ====================

@app.route('/api/join-requests')
@login_required
def get_all_join_requests():
    """Barcha join requestlar"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Database mavjud emas'
            }), 500
        
        all_requests = []
        
        # Barcha startuplar
        active_startups, _ = get_active_startups(1, 100)
        pending_startups, _ = get_pending_startups(1, 100)
        startups = active_startups + pending_startups
        
        for startup in startups:
            startup_id = str(startup.get('_id', ''))
            requests = get_join_requests(startup_id)
            for req in requests:
                user = get_user(req.get('user_id'))
                req['startup_name'] = startup.get('name')
                req['user_name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}" if user else "Noma'lum"
                all_requests.append(req)
        
        return jsonify({
            'success': True,
            'data': all_requests[:50]  # Faqat 50 tasi
        })
    except Exception as e:
        logger.error(f"Join requests error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notifications')
@login_required
def get_notifications():
    """Bildirishnomalar"""
    try:
        # So'nggi faoliyatlar
        recent_startups = get_recent_startups(10)
        recent_users = get_recent_users(10)
        
        notifications = []
        
        # Yangi startaplar
        for startup in recent_startups:
            if startup.get('status') == 'pending':
                notifications.append({
                    'id': str(startup.get('_id', '')),
                    'type': 'new_startup',
                    'title': f"Yangi startup: {startup.get('name', '')}",
                    'message': f"Yangi startup yaratildi: {startup.get('name', '')}",
                    'timestamp': format_date_for_display(startup.get('created_at', '')),
                    'read': False
                })
        
        # Yangi foydalanuvchilar
        for user in recent_users:
            notifications.append({
                'id': str(user.get('user_id', '')),
                'type': 'new_user',
                'title': f"Yangi foydalanuvchi: {user.get('first_name', '')} {user.get('last_name', '')}",
                'message': f"Yangi foydalanuvchi ro'yxatdan o'tdi",
                'timestamp': format_date_for_display(user.get('joined_at', '')),
                'read': False
            })
        
        # Sort by timestamp
        notifications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'data': notifications[:20]  # Faqat 20 tasi
        })
    except Exception as e:
        logger.error(f"Notifications error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== STATIC FILES ====================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Static fayllarni yuklash"""
    return send_from_directory('static', filename)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Sahifa topilmadi'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {traceback.format_exc()}")
    return jsonify({'success': False, 'error': 'Ichki server xatosi'}), 500

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'success': False, 'error': 'Kirish talab qilinadi'}), 401

@app.errorhandler(403)
def forbidden(error):
    return jsonify({'success': False, 'error': 'Ruxsat yo\'q'}), 403

# ==================== MAIN ====================

if __name__ == '__main__':
    # Database ni ishga tushirish
    if DB_AVAILABLE:
        try:
            init_db()
            print("✅ Database ishga tushirildi")
        except Exception as e:
            print(f"⚠️ Database ishga tushirishda xato: {e}")
    else:
        print("⚠️ Database mavjud emas")
    
    # Botni alohida threadda ishga tushirish
    if BOT_AVAILABLE:
        try:
            bot_thread = threading.Thread(target=start_bot, daemon=True)
            bot_thread.start()
            print("✅ Bot thread ishga tushirildi")
        except Exception as e:
            print(f"⚠️ Bot thread ishga tushirishda xato: {e}")
    else:
        print("⚠️ Bot mavjud emas")
    
    # Portni environment dan olish yoki default
    port = int(os.environ.get('PORT', 5000))
    
    # Flask serverni ishga tushirish
    print(f"\n" + "="*50)
    print(f"🚀 GarajHub Admin Panel")
    print(f"="*50)
    print(f"🌐 http://localhost:{port}")
    print(f"📊 Admin panel: http://localhost:{port}")
    print(f"🤖 Bot status: {'✅ Online' if BOT_AVAILABLE else '❌ Offline'}")
    print(f"🗄️ Database status: {'✅ Online' if DB_AVAILABLE else '❌ Offline'}")
    print(f"👤 Admin login: admin / admin123")
    print(f"👤 Moderator login: moderator / moderator123")
    print(f"="*50 + "\n")
    
    # Development mode
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
    
