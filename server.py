import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from functools import wraps
import threading
import time
from bson import ObjectId

# Database import - bu asosiy fayl
try:
    from db import (
        init_db,
        get_user, save_user, update_user_field,
        create_startup, get_startup, get_startups_by_owner,
        get_pending_startups, get_active_startups, update_startup_status,
        get_statistics, get_all_users, get_recent_users, get_recent_startups,
        get_completed_startups, get_rejected_startups
    )
    DB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Database import xatosi: {e}")
    DB_AVAILABLE = False

# Bot import - bu alohida fayl
try:
    from main import bot
    BOT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Bot import xatosi: {e}")
    BOT_AVAILABLE = False

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'garajhub-admin-secret-key-2024')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

CORS(app)

# Logger sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adminlar ro'yxati
ADMINS = {
    'admin': {
        'password': 'admin123',
        'full_name': 'Super Admin',
        'email': 'admin@garajhub.uz',
        'role': 'superadmin'
    }
}

# Login talab qiluvchi decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Botni ishga tushirish funksiyasi
def start_bot():
    if BOT_AVAILABLE:
        try:
            print("🤖 Telegram bot ishga tushmoqda...")
            bot.infinity_polling()
        except Exception as e:
            print(f"Bot xatosi: {e}")
    else:
        print("⚠️ Bot kodi topilmadi")

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
            return jsonify({'error': 'Username va password kiriting'}), 400
        
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
            return jsonify({'error': 'Noto\'g\'ri login yoki parol'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Server xatosi'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout API"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/check_auth')
def check_auth():
    """Auth tekshirish"""
    if 'admin_logged_in' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'username': session.get('admin_username'),
                'full_name': session.get('admin_name'),
                'role': session.get('admin_role')
            }
        })
    return jsonify({'authenticated': False})

@app.route('/api/statistics')
@login_required
def get_statistics_data():
    """Statistika ma'lumotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': True,
                'data': demo_statistics()
            })
        
        stats = get_statistics()
        
        # Bugungi yangi foydalanuvchilar
        today = datetime.now().strftime('%Y-%m-%d')
        recent_users = get_recent_users(100)
        new_today = sum(1 for user in recent_users if user.get('joined_at', '').startswith(today))
        
        # Faollik darajasi
        activity_rate = 75  # Demo uchun
        
        # Trend ma'lumotlari
        trend_data = {
            'users': '+12.5%',
            'startups': '+8.3%',
            'active': '+5.2%'
        }
        
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
                'activity_rate': activity_rate,
                'trends': trend_data
            }
        })
    except Exception as e:
        logger.error(f"Statistics error: {str(e)}")
        return jsonify({
            'success': False,
            'data': demo_statistics()
        })

def demo_statistics():
    """Demo statistika ma'lumotlari"""
    return {
        'total_users': 125,
        'total_startups': 42,
        'active_startups': 18,
        'pending_startups': 8,
        'completed_startups': 12,
        'rejected_startups': 4,
        'new_today': 7,
        'activity_rate': 75,
        'trends': {
            'users': '+12.5%',
            'startups': '+8.3%',
            'active': '+5.2%'
        }
    }

@app.route('/api/users')
@login_required
def get_users():
    """Foydalanuvchilar ro'yxati"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': True,
                'data': demo_users(),
                'pagination': {
                    'page': 1,
                    'per_page': 20,
                    'total': 3,
                    'total_pages': 1
                }
            })
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        filter_type = request.args.get('filter', 'all')
        
        # DB dan foydalanuvchilarni olish
        users = get_recent_users(1000)
        
        # Filtrlash
        if search:
            users = [u for u in users if search.lower() in u.get('first_name', '').lower() or 
                    search.lower() in u.get('last_name', '').lower()]
        
        # Pagination
        total = len(users)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_users = users[start_idx:end_idx]
        
        # Formatlash
        formatted_users = []
        for user in paginated_users:
            formatted_users.append({
                'id': str(user.get('_id', user.get('user_id', ''))),
                'first_name': user.get('first_name', 'Noma\'lum'),
                'last_name': user.get('last_name', ''),
                'phone': user.get('phone', '+998 ** *** ** **'),
                'joined_at': user.get('joined_at', ''),
                'status': 'active' if user.get('user_id') else 'inactive'
            })
        
        return jsonify({
            'success': True,
            'data': formatted_users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        logger.error(f"Users error: {str(e)}")
        return jsonify({
            'success': False,
            'data': [],
            'pagination': {
                'page': 1,
                'per_page': 20,
                'total': 0,
                'total_pages': 0
            }
        })

def demo_users():
    """Demo foydalanuvchilar"""
    return [
        {
            'id': '1',
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone': '+998901234567',
            'joined_at': '2024-01-15',
            'status': 'active'
        },
        {
            'id': '2',
            'first_name': 'Dilnoza',
            'last_name': 'Rahimova',
            'phone': '+998901234568',
            'joined_at': '2024-01-14',
            'status': 'active'
        },
        {
            'id': '3',
            'first_name': 'Shavkat',
            'last_name': 'Karimov',
            'phone': '+998901234569',
            'joined_at': '2024-01-13',
            'status': 'active'
        }
    ]

@app.route('/api/startups')
@login_required
def get_startups_list():
    """Startaplar ro'yxati"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': True,
                'data': demo_startups(),
                'pagination': {
                    'page': 1,
                    'per_page': 20,
                    'total': 3,
                    'total_pages': 1
                }
            })
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '')
        status = request.args.get('status', 'all')
        
        # DB dan startaplarni olish
        if status == 'active':
            startups_data, total = get_active_startups(page, per_page)
            total_pages = (total + per_page - 1) // per_page
        elif status == 'pending':
            startups_data, total = get_pending_startups(page, per_page)
            total_pages = (total + per_page - 1) // per_page
        elif status == 'completed':
            startups_data, total = get_completed_startups(page, per_page)
            total_pages = (total + per_page - 1) // per_page
        elif status == 'rejected':
            startups_data, total = get_rejected_startups(page, per_page)
            total_pages = (total + per_page - 1) // per_page
        else:
            # Barcha startaplar
            all_startups = []
            
            # Har bir holat bo'yicha olish
            active, active_total = get_active_startups(1, 1000)
            pending, pending_total = get_pending_startups(1, 1000)
            completed, completed_total = get_completed_startups(1, 1000)
            rejected, rejected_total = get_rejected_startups(1, 1000)
            
            all_startups = active + pending + completed + rejected
            total = len(all_startups)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            startups_data = all_startups[start_idx:end_idx]
            total_pages = (total + per_page - 1) // per_page
        
        # Formatlash
        formatted_startups = []
        for startup in startups_data:
            # Muallif ma'lumotlari
            owner = get_user(startup.get('owner_id')) if startup.get('owner_id') else None
            owner_name = "Noma'lum"
            if owner:
                owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
                if not owner_name:
                    owner_name = f"User {startup.get('owner_id')}"
            
            # Status matni
            status_texts = {
                'pending': 'Kutilmoqda',
                'active': 'Faol',
                'completed': 'Yakunlangan',
                'rejected': 'Rad etilgan'
            }
            
            formatted_startups.append({
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', 'Noma\'lum'),
                'owner_name': owner_name,
                'owner_id': startup.get('owner_id', ''),
                'status': startup.get('status', 'pending'),
                'status_text': status_texts.get(startup.get('status', 'pending'), startup.get('status', 'pending')),
                'created_at': startup.get('created_at', ''),
                'description': startup.get('description', '')[:100] + '...' if startup.get('description') else '',
                'member_count': 0  # Demo uchun
            })
        
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
        logger.error(f"Startups error: {str(e)}")
        return jsonify({
            'success': False,
            'data': demo_startups(),
            'pagination': {
                'page': 1,
                'per_page': 20,
                'total': 3,
                'total_pages': 1
            }
        })

def demo_startups():
    """Demo startaplar"""
    return [
        {
            'id': '1',
            'name': 'Food Delivery App',
            'owner_name': 'Ali Valiyev',
            'owner_id': '1',
            'status': 'active',
            'status_text': 'Faol',
            'created_at': '2024-01-10',
            'description': 'Oziq-ovqat yetkazib berish ilovasi',
            'member_count': 5
        },
        {
            'id': '2',
            'name': 'E-commerce Platform',
            'owner_name': 'Dilnoza Rahimova',
            'owner_id': '2',
            'status': 'pending',
            'status_text': 'Kutilmoqda',
            'created_at': '2024-01-12',
            'description': 'Onlayn do\'kon platformasi',
            'member_count': 3
        },
        {
            'id': '3',
            'name': 'Education App',
            'owner_name': 'Shavkat Karimov',
            'owner_id': '3',
            'status': 'completed',
            'status_text': 'Yakunlangan',
            'created_at': '2024-01-08',
            'description': 'Masofaviy ta\'lim platformasi',
            'member_count': 8
        }
    ]

@app.route('/api/startup/<startup_id>', methods=['GET'])
@login_required
def get_startup_details(startup_id):
    """Startap tafsilotlari"""
    try:
        if not DB_AVAILABLE:
            return jsonify({
                'success': True,
                'data': demo_startup_detail(startup_id)
            })
        
        startup = get_startup(startup_id)
        if not startup:
            return jsonify({'success': False, 'error': 'Startap topilmadi'}), 404
        
        # Muallif ma'lumotlari
        owner = get_user(startup.get('owner_id')) if startup.get('owner_id') else None
        owner_info = None
        if owner:
            owner_info = {
                'id': owner.get('user_id'),
                'first_name': owner.get('first_name', ''),
                'last_name': owner.get('last_name', ''),
                'phone': owner.get('phone', ''),
                'username': owner.get('username', ''),
                'bio': owner.get('bio', '')
            }
        
        # Status matni
        status_texts = {
            'pending': '⏳ Kutilmoqda',
            'active': '▶️ Faol',
            'completed': '✅ Yakunlangan',
            'rejected': '❌ Rad etilgan'
        }
        
        return jsonify({
            'success': True,
            'data': {
                'id': str(startup.get('_id', '')),
                'name': startup.get('name', ''),
                'description': startup.get('description', ''),
                'status': startup.get('status', ''),
                'status_text': status_texts.get(startup.get('status'), startup.get('status')),
                'created_at': startup.get('created_at', ''),
                'started_at': startup.get('started_at', ''),
                'ended_at': startup.get('ended_at', ''),
                'results': startup.get('results', ''),
                'group_link': startup.get('group_link', ''),
                'logo': startup.get('logo', ''),
                'owner': owner_info
            }
        })
    except Exception as e:
        logger.error(f"Startup details error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def demo_startup_detail(startup_id):
    """Demo startap ma'lumotlari"""
    return {
        'id': startup_id,
        'name': 'Food Delivery App',
        'description': 'Oziq-ovqat yetkazib berish ilovasi. Restoranlar va foydalanuvchilar o\'rtasida platforma.',
        'status': 'active',
        'status_text': '▶️ Faol',
        'created_at': '2024-01-10 14:30:00',
        'started_at': '2024-01-12 10:00:00',
        'ended_at': None,
        'results': '',
        'group_link': 'https://t.me/fooddeliverygroup',
        'logo': '',
        'owner': {
            'id': '1',
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone': '+998901234567',
            'username': 'alivaliyev',
            'bio': 'Startup asoschisi'
        }
    }

@app.route('/api/startup/<startup_id>/approve', methods=['POST'])
@login_required
def approve_startup(startup_id):
    """Startapni tasdiqlash"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': True, 'message': 'Startap tasdiqlandi (demo)'})
        
        update_startup_status(startup_id, 'active')
        logger.info(f"Startup approved: {startup_id}")
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if startup and startup.get('owner_id'):
                    bot.send_message(
                        startup['owner_id'],
                        f"🎉 Tabriklaymiz! Sizning '{startup['name']}' startupingiz tasdiqlandi!"
                    )
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
        
        return jsonify({'success': True, 'message': 'Startap tasdiqlandi'})
    except Exception as e:
        logger.error(f"Approve startup error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/startup/<startup_id>/reject', methods=['POST'])
@login_required
def reject_startup(startup_id):
    """Startapni rad etish"""
    try:
        if not DB_AVAILABLE:
            return jsonify({'success': True, 'message': 'Startap rad etildi (demo)'})
        
        update_startup_status(startup_id, 'rejected')
        logger.info(f"Startup rejected: {startup_id}")
        
        # Bot orqali xabar yuborish
        if BOT_AVAILABLE:
            try:
                startup = get_startup(startup_id)
                if startup and startup.get('owner_id'):
                    bot.send_message(
                        startup['owner_id'],
                        f"❌ Sizning '{startup['name']}' startupingiz rad etildi."
                    )
            except Exception as e:
                logger.error(f"Bot orqali xabar yuborishda xato: {e}")
        
        return jsonify({'success': True, 'message': 'Startap rad etildi'})
    except Exception as e:
        logger.error(f"Reject startup error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/broadcast', methods=['POST'])
@login_required
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
        if BOT_AVAILABLE and DB_AVAILABLE:
            try:
                users = get_all_users()
                for user_id in users:
                    try:
                        bot.send_message(user_id, f"📢 Yangilik!\n\n{message}")
                        sent_count += 1
                        time.sleep(0.1)  # Flood dan qochish
                    except Exception as e:
                        logger.error(f"Foydalanuvchiga xabar yuborishda xato {user_id}: {e}")
            except Exception as e:
                logger.error(f"Xabar yuborishda xato: {e}")
        
        logger.info(f"Broadcast message: {message[:50]}... (to: {recipient_type}, sent: {sent_count})")
        
        return jsonify({
            'success': True,
            'message': 'Xabar yuborildi',
            'data': {
                'id': str(ObjectId()),
                'message': message[:100] + '...' if len(message) > 100 else message,
                'recipient_type': recipient_type,
                'sent_at': datetime.now().isoformat(),
                'sent_by': session.get('admin_username'),
                'sent_count': sent_count
            }
        })
    except Exception as e:
        logger.error(f"Broadcast error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/user-growth')
@login_required
def get_user_growth():
    """Foydalanuvchi o'sishi uchun analytics"""
    try:
        period = request.args.get('period', 'month')
        
        # Demo ma'lumotlar
        now = datetime.now()
        data = []
        labels = []
        
        if period == 'week':
            # Oxirgi 7 kun
            for i in range(6, -1, -1):
                date = now - timedelta(days=i)
                labels.append(date.strftime('%d.%m'))
                data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'new_users': max(0, (10 - i) + (i % 3)),
                    'total_users': 100 + i * 5
                })
        else:
            # Default: oxirgi 30 kun
            for i in range(29, -1, -1):
                date = now - timedelta(days=i)
                labels.append(date.strftime('%d.%m') if i % 5 == 0 else '')
                data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'new_users': max(0, (15 - i // 2) + (i % 7)),
                    'total_users': 100 + i * 3
                })
        
        return jsonify({
            'success': True,
            'data': {
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Yangi foydalanuvchilar',
                        'data': [d['new_users'] for d in data],
                        'borderColor': '#000000',
                        'backgroundColor': 'rgba(0, 0, 0, 0.1)',
                        'tension': 0.4
                    },
                    {
                        'label': 'Jami foydalanuvchilar',
                        'data': [d['total_users'] for d in data],
                        'borderColor': '#666666',
                        'backgroundColor': 'transparent',
                        'tension': 0.4,
                        'hidden': True
                    }
                ]
            }
        })
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/startup-distribution')
@login_required
def get_startup_distribution():
    """Startap taqsimoti"""
    try:
        if not DB_AVAILABLE:
            stats = demo_statistics()
        else:
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
                    '#000000',  # Faol - qora
                    '#666666',  # Kutilayotgan - kulrang
                    '#999999',  # Yakunlangan - och kulrang
                    '#CCCCCC'   # Rad etilgan - ochroq kulrang
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
        logger.error(f"Distribution error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/activity')
@login_required
def get_recent_activity():
    """So'nggi faollik"""
    try:
        # Demo faollik ma'lumotlari
        activities = []
        types = ['user', 'startup', 'message', 'system']
        actions = ['yaratildi', 'tasdiqlandi', 'yangilandi', 'o\'chirildi', 'xabar yuborildi']
        
        for i in range(10):
            activity_type = types[i % len(types)]
            action = actions[i % len(actions)]
            time_ago = f"{i * 2} daqiqa oldin" if i > 0 else "Hozirgina"
            
            activities.append({
                'id': i + 1,
                'type': activity_type,
                'action': action,
                'description': f"{activity_type.capitalize()} {action}",
                'time_ago': time_ago,
                'icon': 'user' if activity_type == 'user' else 'rocket' if activity_type == 'startup' else 'envelope'
            })
        
        return jsonify({
            'success': True,
            'data': activities
        })
    except Exception as e:
        logger.error(f"Activity error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Sozlamalar"""
    try:
        if request.method == 'GET':
            # Demo sozlamalar
            return jsonify({
                'success': True,
                'data': {
                    'site_name': 'GarajHub',
                    'admin_email': 'admin@garajhub.uz',
                    'timezone': 'Asia/Tashkent',
                    'bot_token': '8265294721:AAEWhiYC2zTYxPbFpYYFezZGNzKHUumoplE',
                    'channel_username': '@GarajHub_uz',
                    'bot_status': 'online' if BOT_AVAILABLE else 'offline'
                }
            })
        else:
            # Sozlamalarni yangilash
            data = request.json
            logger.info(f"Settings updated: {data}")
            
            # Bu yerda sozlamalarni saqlash logikasi bo'lishi kerak
            # Hozircha faqat log qilamiz
            
            return jsonify({'success': True, 'message': 'Sozlamalar saqlandi'})
    except Exception as e:
        logger.error(f"Settings error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admins')
@login_required
def get_admins():
    """Adminlar ro'yxati"""
    try:
        # Demo adminlar
        admins = [
            {
                'id': 1,
                'username': 'admin',
                'full_name': 'Super Admin',
                'email': 'admin@garajhub.uz',
                'role': 'superadmin',
                'last_login': datetime.now().isoformat(),
                'created_at': '2024-01-01'
            },
            {
                'id': 2,
                'username': 'moderator',
                'full_name': 'Moderator',
                'email': 'moderator@garajhub.uz',
                'role': 'admin',
                'last_login': (datetime.now() - timedelta(days=1)).isoformat(),
                'created_at': '2024-01-15'
            }
        ]
        
        return jsonify({
            'success': True,
            'data': admins
        })
    except Exception as e:
        logger.error(f"Admins error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backups')
@login_required
def get_backups():
    """Backup ma'lumotlari"""
    try:
        # Demo backup ma'lumotlari
        backups = []
        for i in range(5):
            backups.append({
                'id': i + 1,
                'filename': f'backup_2024_01_{i+10}.json',
                'size': f'{1.5 + i * 0.3:.1f} MB',
                'created_at': (datetime.now() - timedelta(days=i)).isoformat(),
                'created_by': 'admin'
            })
        
        return jsonify({
            'success': True,
            'data': backups
        })
    except Exception as e:
        logger.error(f"Backups error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Sahifa topilmadi'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Ichki server xatosi'}), 500

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
        print("⚠️ Database mavjud emas, demo rejimda ishlaydi")
    
    # Botni alohida threadda ishga tushirish
    if BOT_AVAILABLE:
        try:
            bot_thread = threading.Thread(target=start_bot, daemon=True)
            bot_thread.start()
            print("✅ Bot thread ishga tushirildi")
        except Exception as e:
            print(f"⚠️ Bot thread ishga tushirishda xato: {e}")
    else:
        print("⚠️ Bot mavjud emas, faqat web panel ishlaydi")
    
    # Portni environment dan olish yoki default
    port = int(os.environ.get('PORT', 5000))
    
    # Flask serverni ishga tushirish
    print(f"🚀 Web admin panel ishga tushmoqda...")
    print(f"🌐 http://localhost:{port}")
    print(f"📊 Admin panel: http://localhost:{port}")
    print(f"🤖 Bot status: {'Online' if BOT_AVAILABLE else 'Offline'}")
    print(f"🗄️ Database status: {'Online' if DB_AVAILABLE else 'Demo mode'}")
    
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)