

import random
import smtplib
from email.message import EmailMessage
from PyQt5.QtWidgets import QMessageBox

global otp
otp = ""
def OTP_gen():
    global otp
    otp = ""
    i = 0
    for _ in range(6):
        if i == 3:
            otp += "-"
        otp += str(random.randint(0, 9))
        i += 1
    return otp

def email_send(email):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        from_mail = 'aliabdullahawan.2003@gmail.com'
        server.login(from_mail, 'soil oozf fjcg beqt')
        msg = EmailMessage()
        msg['Subject'] = 'Your OTP Code'
        msg['From'] = from_mail
        msg['To'] = email
        global otp
        otp = OTP_gen()
        msg.set_content(f"""
        Welcome to RETRO RELOAD!
        
        Your One-Time Password (OTP) is: {otp}
        
        This code will expire in 10 minutes.
        Please do not share this code with anyone.
        
        If you did not request this code, please ignore this email.
        
        Thank you,
        RETRO RELOAD Team
        """)
        server.send_message(msg)
        server.quit()
        QMessageBox.information(None, "Info", "Email sent successfully.")
    except smtplib.SMTPRecipientsRefused:
        QMessageBox.warning(None, "Error", "Invalid recipient email address!")
