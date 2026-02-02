import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.config import Config
from utils.utils import setup_logger

logger = setup_logger(__name__)

class MailService:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = Config.EMAIL_SENDER
        self.password = Config.EMAIL_PASSWORD
        self.enabled = bool(self.sender_email and self.password)

    def send_dose_reminder(self, to_email, medicine_name, dosage, instructions, time_str):
        if not self.enabled:
            logger.warning("Email service disabled: Credentials missing.")
            return False

        try:
            subject = f"💊 Reminder: Time for {medicine_name}"
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                        <h2 style="color: #008080;">Time to take your medication</h2>
                        <p>Hello,</p>
                        <p>This is a reminder to take the following medication scheduled for <strong>{time_str}</strong>:</p>
                        
                        <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #008080; margin: 20px 0;">
                            <h3 style="margin: 0; color: #008080;">{medicine_name}</h3>
                            <p style="margin: 5px 0 0;"><strong>Dosage:</strong> {dosage}</p>
                            {f'<p style="margin: 5px 0 0;"><strong>Instructions:</strong> {instructions}</p>' if instructions else ''}
                        </div>
                        
                        <p>Please log this in your <a href="#" style="color: #008080;">pharmEZ Dashboard</a>.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <small style="color: #666;">pharmEZ Health Assistant</small>
                    </div>
                </body>
            </html>
            """
            
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email} for {medicine_name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
