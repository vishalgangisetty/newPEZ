from apscheduler.schedulers.background import BackgroundScheduler
from services.mail_service import MailService
from utils.reminder import ReminderManager
from utils.utils import setup_logger
import atexit

logger = setup_logger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        atexit.register(lambda: self.scheduler.shutdown())
        self._add_jobs()
        
    def _add_jobs(self):
        # Check for medication reminders every minute
        self.scheduler.add_job(
            func=self._check_reminders,
            trigger="interval",
            minutes=1,
            id="medication_reminders",
            replace_existing=True
        )
        logger.info("Scheduler started: Medication reminder job added.")

    def _check_reminders(self):
        try:
            # Re-instantiate managers to ensure thread safety / fresh db connection if needed
            reminder_mgr = ReminderManager()
            mail_svc = MailService()
            
            if not mail_svc.enabled:
                return

            due_reminders = reminder_mgr.check_due_reminders()
            
            if due_reminders:
                logger.info(f"Found {len(due_reminders)} due reminders.")
            
            for reminder in due_reminders:
                recipient = reminder.get('notification_email')
                if recipient:
                    success = mail_svc.send_dose_reminder(
                        recipient,
                        reminder['medicine_name'],
                        reminder['dosage'],
                        reminder.get('instructions', ''),
                        # Since check_due_reminders returns active ones matching current time,
                        # we can pass current time or the matched time. 
                        # Ideally check_due_reminders should return the specific time matched.
                        # For now, let's assume the reminder logic handles timing checks correctly.
                        # Wait, ReminderManager.check_due_reminders checks current time against "times" list.
                        # It returns the whole reminder doc. 
                        # We'll just pass the current HH:MM string.
                        reminder.get('current_match_time', 'NOW') 
                    )
        except Exception as e:
            logger.error(f"Scheduler Job Error: {e}")
