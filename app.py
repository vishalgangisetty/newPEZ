from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import uuid
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename

# --- Services & Utils ---
from utils.auth import AuthManager
from utils.reminder import ReminderManager
from utils.pharmacy_locator import PharmacyLocator
from utils.otc_manager import OTCManager
from utils.utils import setup_logger, ensure_directory
from utils.extractor import PrescriptionExtractor
from utils.vector_store import VectorStoreManager
from utils.memory import MemoryManager
from services.scheduler import SchedulerService
from services.validator import Validator

try:
    from utils.graph import RAGGraph
except ImportError:
    RAGGraph = None

# --- App Config ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "pharmEZ_secret_key_2026")
logger = setup_logger(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'data', 'input')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg'}
ensure_directory(UPLOAD_FOLDER)

# --- Initialize Core Services ---
auth_manager = AuthManager()
reminder_manager = ReminderManager()
pharmacy_locator = PharmacyLocator()
otc_manager = OTCManager()
extractor = PrescriptionExtractor()
vector_store = VectorStoreManager()
memory_manager = MemoryManager()
scheduler_service = SchedulerService() # Starts background scheduler

rag_graph = None
try:
    if RAGGraph:
        rag_graph = RAGGraph().build_graph()
except Exception as e:
    logger.error(f"RAG Init Error: {e}")

# --- Helper Logic ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Error Handling ---
@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error="Internal Server Error"), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error="Page Not Found"), 404

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled Exception: {e}", exc_info=True)
    return render_template('error.html', error=str(e)), 500

# --- Routes ---
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        
        valid_err = Validator.validate_login(username, password)
        if valid_err:
            flash(valid_err, "danger")
            return render_template('index.html')

        if action == 'register':
            success, msg = auth_manager.register_user(username, password)
            if success:
                flash("Account created! Please login.", "success")
            else:
                flash(msg, "danger")
        else:
            success, msg = auth_manager.login_user(username, password)
            if success:
                session['user'] = username
                return redirect(url_for('dashboard'))
            else:
                flash(msg, "danger")
                
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    user = session['user']
    
    if request.method == 'POST':
        if 'prescription' in request.files:
            file = request.files['prescription']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # Check duplication
                existing_id = memory_manager.get_prescription_by_filename(user, filename)
                if existing_id:
                    flash("Prescription already exists.", "info")
                    return redirect(url_for('dashboard', view=existing_id))
                
                file_id = str(uuid.uuid4())
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                
                try:
                    data = extractor.extract_data(file_path)
                    if data:
                        med_details = []
                        for m in data.get('medicines', []):
                            timing = m.get('timing', {})
                            timing_str = f"M:{timing.get('morning')} A:{timing.get('afternoon')} N:{timing.get('night')}"
                            med_details.append(f"- {m.get('name')} {m.get('dosage')}: {timing_str}")
                        
                        meds_str = "\n".join(med_details)
                        full_text = f"Date: {data.get('date')}\n{meds_str}\nNotes: {data.get('notes')}"
                        
                        vector_store.add_prescription(file_id, [full_text], {"filename": filename})
                        
                        title = f"Rx: {filename}"
                        if data.get('medicines'):
                            title = f"Rx: {data['medicines'][0].get('name')}..."
                            
                        memory_manager.get_or_create_session(user, file_id, title=title, filename=filename, details=meds_str)
                        flash("Prescription analyzed successfully!", "success")
                        return redirect(url_for('dashboard', view=file_id))
                    else:
                        flash("Could not extract data from file.", "warning")
                except Exception as e:
                    logger.error(f"Processing Error: {e}")
                    flash(f"Error processing prescription: {e}", "danger")

    prescriptions = memory_manager.get_user_prescriptions(user)
    
    active_id = request.args.get('view')
    active_p = None
    chat_history = []
    
    if active_id:
        active_p = next((p for p in prescriptions if p['id'] == active_id), None)
        if active_p:
            sess_id = memory_manager.get_or_create_session(user, active_id)
            active_p['details'] = memory_manager.get_session_details(sess_id)
            chat_history = memory_manager.get_history(sess_id)

    return render_template('dashboard.html', 
                           user=user, 
                           prescriptions=prescriptions, 
                           active_p=active_p, 
                           chat_history=chat_history)

@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    data = request.json
    msg = data.get('message')
    pid = data.get('prescription_id')
    
    if not msg or not pid:
        return jsonify({'error': 'Invalid request'}), 400
        
    try:
        sess_id = memory_manager.get_or_create_session(session['user'], pid)
        
        if not rag_graph:
            return jsonify({'answer': 'AI Service Unavailable. Check API keys.'})
            
        result = rag_graph.invoke({
            "question": msg,
            "prescription_id": pid,
            "session_id": sess_id,
            "context": [],
            "answer": ""
        })
        return jsonify({'answer': result.get("answer", "No response generated")})
    except Exception as e:
        logger.error(f"Chat API Error: {e}")
        return jsonify({'answer': f"Error: {str(e)}"}), 500

@app.route('/medications', methods=['GET', 'POST'])
@login_required
def medications():
    if request.method == 'POST':
        # Safely extract form data
        form_data = {
            'name': request.form.get('name'),
            'dosage': request.form.get('dosage'),
            'frequency': request.form.get('frequency'),
            'times': request.form.getlist('times'),
            'duration': int(request.form.get('duration', 7)),
            'start_date': request.form.get('start_date'),
            'email_notification': 'email_notification' in request.form,
            'notification_email': request.form.get('notification_email'),
            'calendar_sync': 'calendar' in request.form
        }
        
        # Validation
        validation_errors = Validator.validate_medication_input(form_data)
        if validation_errors:
            for err in validation_errors:
                flash(err, "danger")
        else:
            try:
                res = reminder_manager.add_reminder(
                    session['user'],
                    form_data['name'],
                    form_data['dosage'],
                    form_data['frequency'],
                    form_data['times'],
                    form_data['duration'],
                    form_data['start_date'],
                    email_notification=form_data['email_notification'],
                    notification_email=form_data['notification_email']
                )
                
                if res['success']:
                    flash("Medication schedule added successfully!", "success")
                    
                    if form_data['calendar_sync']:
                        from utils.calendar_integration import CalendarIntegration
                        cal = CalendarIntegration()
                        if cal.available:
                            # Use first time for simple event logic usually, but here we can iterate
                            # For simplicity in calendar integration call (assuming it handles list or we iterate)
                            # Looking at old code, it handles creating events for duration.
                            # We pass the list of times.
                            cal_res = cal.create_multiple_reminder_events(
                                form_data['name'],
                                form_data['dosage'],
                                form_data['times'],
                                form_data['start_date'],
                                form_data['duration']
                            )
                            if cal_res['success']:
                                flash(f"Synced {cal_res['created']} events to Google Calendar.", "info")
                        else:
                            flash("Google Calendar not configured.", "warning")
                else:
                    flash(f"Error adding reminder: {res.get('error')}", "danger")
            except Exception as e:
                flash(f"System Error: {e}", "danger")
                logger.error(f"Medication Add Error: {e}")
            
    reminders = reminder_manager.get_user_reminders(session['user'])
    # Commenting out stats for now if not needed or problematic, 
    # but the User request implied UI layout fixes so keeping it simple is better.
    # We'll just pass reminders.
    return render_template('medications.html', user=session['user'], reminders=reminders, now=datetime.now().strftime("%Y-%m-%d"))

@app.route('/pharmacy')
@login_required
def pharmacy():
    return render_template('pharmacy.html', user=session['user'])

@app.route('/api/pharmacy/search', methods=['POST'])
@login_required
def pharmacy_search():
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')
    radius = data.get('radius', 5000)
    
    if not lat or not lng:
        return jsonify({'error': 'Missing coordinates'}), 400
        
    try:
        results = pharmacy_locator.find_nearby_pharmacies(float(lat), float(lng), int(radius))
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/safety')
@login_required
def safety():
    query = request.args.get('q')
    results = []
    if query:
        results = otc_manager.search_otc_db(query)
    else:
        results = otc_manager.get_otc_list()
    return render_template('safety.html', user=session['user'], results=results, query=query)

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False) # Loader false for scheduler
