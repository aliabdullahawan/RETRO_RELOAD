import sys
import os  # REQUIRED FOR PATH FINDING
import re
import pyodbc
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox, QLineEdit, QDialog, QVBoxLayout, QLabel, QPushButton

from User import UserWindow
from Publisher import PublisherWindow
from Admin import AdminWindow

try:
    import OTP
except ImportError:
    OTP = None 

# --- RESOURCE PATH FUNCTION (FIX FOR EXE) ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # IN DEVELOPMENT: Use the folder where this python file is located
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class UserObject:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class DatabaseManager:
    def __init__(self, config=None):
        self.conn_str = ""
        if config:
            self.conn_str = f'Driver={{ODBC Driver 18 for SQL Server}};Server={config["server"]},{config["port"]};Database=RETRO_RELOAD;UID={config["uid"]};PWD={config["pwd"]};Encrypt=no;TrustServerCertificate=yes;'
        else:
            print("DB Error: No configuration provided via Startup.")

    def get_connection(self):
        try:
            if not self.conn_str: return None
            return pyodbc.connect(self.conn_str)
        except Exception as e:
            print(f"DB Error: {e}")
            return None

    def validate_login(self, email, password, role):
        conn = self.get_connection()
        if not conn: return None, "Database Connection Failed"
        cursor = conn.cursor()
        try:
            cursor.execute("EXEC sp_UserLogin ?, ?, ?", (email, password, role))
            row = cursor.fetchone()
            
            if not row:
                return None, "Invalid Email, Password, or Role."
            
            user_obj = UserObject(
                id=row.User_ID,
                first_name=row.User_fname,
                last_name=row.User_Lname,
                username=row.User_username,
                email=row.User_Email,
                role=row.Role,
                balance=float(row.Wallet_Balance) if row.Wallet_Balance else 0.0,
                password=getattr(row, 'User_Password', ''),
                card=getattr(row, 'Card_Number', '')
            )
            return user_obj, "Success"
            
        except Exception as e:
            return None, f"Login Error: {e}"
        finally:
            conn.close()

    def register_user(self, fname, lname, username, email, password, card, role):
        conn = self.get_connection()
        if not conn: return None
        cursor = conn.cursor()
        try:
            cursor.execute("EXEC sp_UserRegister ?, ?, ?, ?, ?, ?, ?", (fname, lname, username, email, password, card, role))
            row = cursor.fetchone()
            if row:
                conn.commit()
                return row[0]
            return None
        except Exception as e:
            print("Register Error:", e)
            return None
        finally:
            conn.close()

    def update_password(self, email, new_password):
        conn = self.get_connection()
        if not conn: return False
        cursor = conn.cursor()
        try:
            cursor.execute("EXEC sp_UpdatePassword ?, ?", (email, new_password))
            conn.commit()
            return True
        except Exception as e:
            print("Update Password Error:", e)
            return False
        finally:
            conn.close()

class OTPDialog(QDialog):
    def __init__(self, parent=None, email=""):
        super().__init__(parent)
        self.setWindowTitle("Verify OTP")
        self.setFixedSize(300, 200)
        self.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        lbl = QLabel(f"OTP sent to:\n{email}")
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet("color: #555; font-size: 14px;")
        layout.addWidget(lbl)
        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("XXX-XXX") 
        self.otp_input.setAlignment(QtCore.Qt.AlignCenter)
        self.otp_input.setMaxLength(7) 
        self.otp_input.setStyleSheet("border: 2px solid #3498db; border-radius: 5px; padding: 10px; font-size: 16px; font-weight: bold; letter-spacing: 2px;")
        self.otp_input.textChanged.connect(self.format_otp)
        layout.addWidget(self.otp_input)
        btn = QPushButton("Verify")
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border-radius: 5px; padding: 10px; font-weight: bold; font-size: 14px; } QPushButton:hover { background-color: #2ecc71; }")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def format_otp(self, text):
        raw = text.replace("-", "")
        formatted = raw
        if len(raw) > 3: formatted = raw[:3] + "-" + raw[3:]
        if self.otp_input.text() != formatted:
            self.otp_input.setText(formatted)
            self.otp_input.setCursorPosition(len(formatted))

    def get_otp(self):
        return self.otp_input.text().replace("-", "").strip()

class LoginWindow(QtWidgets.QMainWindow):
    def __init__(self, db_config=None):
        super().__init__()
        self.db_config = db_config
        self.setWindowTitle("Login System")
        self.resize(1000, 700)
        self.setStyleSheet("background-color: #f0f2f5;") 
        
        # --- FIX: USE RESOURCE PATH FOR ICON ---
        self.setWindowIcon(QtGui.QIcon(resource_path('Icon.png')))
        
        self.db = DatabaseManager(self.db_config)

        self.centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralwidget)
        self.main_layout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.main_layout.setAlignment(QtCore.Qt.AlignCenter)
        self.card = QtWidgets.QFrame(self.centralwidget)
        self.card.setFixedSize(450, 760) 
        self.card.setStyleSheet("QFrame { background-color: white; border-radius: 20px; border: 1px solid #dcdcdc; }")
        self.card.setFrameShadow(QtWidgets.QFrame.Raised)
        self.card_layout = QtWidgets.QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(40, 40, 40, 40); self.card_layout.setSpacing(15)
        self.title_label = QtWidgets.QLabel("RETRO RELOAD")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #2c3e50; font-size: 28px; font-weight: bold; border: none;")
        self.card_layout.addWidget(self.title_label)
        self.subtitle_label = QtWidgets.QLabel("Welcome Back!")
        self.subtitle_label.setAlignment(QtCore.Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: #7f8c8d; font-size: 16px; border: none;")
        self.card_layout.addWidget(self.subtitle_label)
        self.card_layout.addSpacing(20)
        self.stack = QtWidgets.QStackedWidget(self.card)
        self.stack.setStyleSheet("border: none;")
        self.card_layout.addWidget(self.stack)
        self.createLoginPage()
        self.createRegisterPage()
        self.createForgotPage()
        self.main_layout.addWidget(self.card)
        self.stack.setCurrentIndex(0) 

    def createLoginPage(self):
        page = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(page); layout.setSpacing(15); layout.setContentsMargins(0,0,0,0)
        self.login_email = self.createInput("Email Address"); layout.addWidget(self.login_email)
        self.login_pass = self.createInput("Password", is_password=True); layout.addWidget(self.login_pass)
        self.login_role = QtWidgets.QComboBox(); self.login_role.addItems(["User", "Admin", "Publisher"]); self.styleComboBox(self.login_role); layout.addWidget(self.login_role)
        btn_login = self.createButton("LOGIN", "#2980b9", self.handleLogin); layout.addWidget(btn_login)
        btn_forgot = self.createLinkButton("Forgot Password?", self.goToForgot); layout.addWidget(btn_forgot)
        layout.addStretch()
        footer = QtWidgets.QHBoxLayout(); footer.addWidget(QtWidgets.QLabel("New here?", styleSheet="color: #7f8c8d;")); btn_reg = self.createLinkButton("Create Account", self.goToRegister, color="#e67e22"); footer.addWidget(btn_reg); footer.addStretch(); footer.setAlignment(QtCore.Qt.AlignCenter); layout.addLayout(footer)
        self.stack.addWidget(page)

    def createRegisterPage(self):
        page = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(page); layout.setSpacing(10); layout.setContentsMargins(0,0,0,0)
        row_name = QtWidgets.QHBoxLayout()
        self.reg_fname = self.createInput("First Name")
        self.reg_lname = self.createInput("Last Name")
        row_name.addWidget(self.reg_fname); row_name.addWidget(self.reg_lname)
        layout.addLayout(row_name)
        self.reg_user = self.createInput("Username"); layout.addWidget(self.reg_user)
        self.reg_email = self.createInput("Email Address"); layout.addWidget(self.reg_email)
        self.reg_cr = self.createInput("Credit Card (XXXX XXXX XXXX XXXX)")
        self.reg_cr.textChanged.connect(self.format_credit_card)
        layout.addWidget(self.reg_cr)
        self.reg_pass = self.createInput("Password", is_password=True); layout.addWidget(self.reg_pass)
        self.reg_confirm = self.createInput("Confirm Password", is_password=True); layout.addWidget(self.reg_confirm)
        self.reg_role = QtWidgets.QComboBox()
        self.reg_role.addItems(["User", "Publisher"])
        self.styleComboBox(self.reg_role)
        layout.addWidget(self.reg_role)
        layout.addSpacing(10)
        btn_signup = self.createButton("SIGN UP", "#27ae60", self.handleRegister); layout.addWidget(btn_signup)
        btn_back = self.createLinkButton("Back to Login", self.goToLogin); layout.addWidget(btn_back)
        self.stack.addWidget(page)

    def createForgotPage(self):
        page = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(page); layout.setSpacing(20); layout.setContentsMargins(0,0,0,0)
        info = QtWidgets.QLabel("Enter your email and new password. We will send an OTP."); info.setWordWrap(True); info.setStyleSheet("color: #7f8c8d; font-size: 13px;"); layout.addWidget(info)
        self.forgot_email = self.createInput("Registered Email"); layout.addWidget(self.forgot_email)
        self.forgot_pass = self.createInput("New Password", is_password=True); layout.addWidget(self.forgot_pass)
        layout.addSpacing(10)
        btn_otp = self.createButton("SEND OTP", "#e67e22", self.handleForgot); layout.addWidget(btn_otp)
        btn_back = self.createLinkButton("Back to Login", self.goToLogin); layout.addWidget(btn_back)
        layout.addStretch(); self.stack.addWidget(page)

    def createInput(self, placeholder, is_password=False):
        inp = QLineEdit(); inp.setPlaceholderText(placeholder)
        if is_password: inp.setEchoMode(QLineEdit.Password)
        inp.setStyleSheet("QLineEdit { background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px; font-size: 14px; color: #333; } QLineEdit:focus { border: 1px solid #3498db; background-color: #fff; }")
        return inp
        
    def createButton(self, text, bg_color, callback):
        btn = QPushButton(text); btn.setCursor(QtCore.Qt.PointingHandCursor); btn.clicked.connect(callback)
        btn.setStyleSheet(f"QPushButton {{ background-color: {bg_color}; color: white; font-weight: bold; border-radius: 8px; padding: 12px; font-size: 14px; }} QPushButton:hover {{ opacity: 0.9; }}")
        return btn

    def createLinkButton(self, text, callback, color="#3498db"):
        btn = QPushButton(text); btn.setCursor(QtCore.Qt.PointingHandCursor); btn.clicked.connect(callback)
        btn.setStyleSheet(f"QPushButton {{ background-color: transparent; color: {color}; font-weight: bold; border: none; font-size: 13px; }} QPushButton:hover {{ text-decoration: underline; }}")
        return btn

    def styleComboBox(self, combo):
        combo.setStyleSheet("QComboBox { padding: 8px; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #f9f9f9; color: #333; } QComboBox::drop-down { border: none; }")

    def format_credit_card(self, text):
        cleaned_text = re.sub(r'\D', '', text)
        cleaned_text = cleaned_text[:16]
        formatted_text = ""
        for i in range(0, len(cleaned_text), 4):
            if i + 4 < len(cleaned_text):
                formatted_text += cleaned_text[i:i+4] + " "
            else:
                formatted_text += cleaned_text[i:]
        if self.reg_cr.text() != formatted_text:
            self.reg_cr.blockSignals(True)
            self.reg_cr.setText(formatted_text)
            self.reg_cr.setCursorPosition(len(formatted_text))
            self.reg_cr.blockSignals(False)

    def goToLogin(self): self.subtitle_label.setText("Welcome Back!"); self.stack.setCurrentIndex(0)
    def goToRegister(self): self.subtitle_label.setText("Create Account"); self.stack.setCurrentIndex(1)
    def goToForgot(self): self.subtitle_label.setText("Reset Password"); self.stack.setCurrentIndex(2)

    def validate_email(self, email): return re.match(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', email)
    def validate_password(self, password):
        if len(password) < 8: return False
        if not re.search(r"[a-zA-Z]", password): return False
        if not re.search(r"[0-9]", password): return False
        return True

    def handleLogin(self):
        email = self.login_email.text().strip()
        password = self.login_pass.text().strip()
        role = self.login_role.currentText()
        if not email or not password:
            QMessageBox.warning(self, "Error", "All fields are required.")
            return
        user_obj, message = self.db.validate_login(email, password, role)
        if user_obj:
            if role == "User": self.openUserWindow(user_obj)
            elif role == "Publisher": self.openPublisherWindow(user_obj)
            elif role == "Admin": self.openAdminWindow(user_obj)
        else:
            QMessageBox.warning(self, "Login Failed", message)

    def handleRegister(self):
        fname = self.reg_fname.text().strip(); lname = self.reg_lname.text().strip()
        user = self.reg_user.text().strip(); email = self.reg_email.text().strip()
        cr_info = self.reg_cr.text().strip(); pw = self.reg_pass.text().strip()
        cpw = self.reg_confirm.text().strip(); role = self.reg_role.currentText()
        if not all([fname, lname, user, email, cr_info, pw, cpw]): QMessageBox.warning(self, "Error", "All fields are required."); return
        if not self.validate_email(email): QMessageBox.warning(self, "Error", "Invalid Email. Must be @gmail.com"); return
        clean_cr = cr_info.replace(" ", "")
        if len(clean_cr) != 16 or not clean_cr.isdigit(): QMessageBox.warning(self, "Error", "Invalid Credit Card.\nMust be 16 digits."); return
        if pw != cpw: QMessageBox.warning(self, "Error", "Passwords do not match."); return
        if not self.validate_password(pw): QMessageBox.warning(self, "Error", "Password too weak.\nMust be 8+ chars with letters & numbers."); return
        if self.processOTP(email):
            new_id = self.db.register_user(fname, lname, user, email, pw, clean_cr, role)
            if new_id == -1: QMessageBox.warning(self, "Error", "User already registered with this email.")
            elif new_id:
                full_user_obj = UserObject(id=new_id, first_name=fname, last_name=lname, username=user, email=email, role=role, balance=500.00)
                QMessageBox.information(self, "Success", "Registration Successful!")
                if role == "User": self.openUserWindow(full_user_obj)
                elif role == "Publisher": self.openPublisherWindow(full_user_obj)
                elif role == "Admin": self.openAdminWindow(full_user_obj)
            else: QMessageBox.critical(self, "Error", "Database Error. Could not register.")

    def handleForgot(self):
        email = self.forgot_email.text().strip(); new_pass = self.forgot_pass.text().strip()
        if not email or not new_pass: QMessageBox.warning(self, "Error", "Please enter email and new password."); return
        if not self.validate_email(email): QMessageBox.warning(self, "Error", "Invalid Email format."); return
        if not self.validate_password(new_pass): QMessageBox.warning(self, "Error", "Password too weak."); return
        if self.processOTP(email): 
            if self.db.update_password(email, new_pass):
                QMessageBox.information(self, "Success", "Password updated successfully (if email existed).")
                self.goToLogin()
            else: QMessageBox.critical(self, "Error", "Database error updating password.")

    def processOTP(self, email):
        try:
            if OTP:
                OTP.email_send(email)
                server_otp = str(OTP.otp).strip() 
            else:
                server_otp = "123-456"
            dlg = OTPDialog(self, email)
            if dlg.exec_() == QDialog.Accepted:
                user_otp = dlg.get_otp() 
                if user_otp.replace("-", "") == server_otp.replace("-", ""): return True
                else: QMessageBox.warning(self, "Error", "Invalid OTP entered."); return False
            return False
        except Exception as e:
            QMessageBox.critical(self, "OTP Error", f"Error interacting with OTP module: {e}"); return False

    def openUserWindow(self, user_obj):
        self.hide()
        self.user_win = UserWindow(user_obj, self.db_config) 
        self.user_win.show()

    def openPublisherWindow(self, user_obj):
        self.hide()
        self.pub_win = PublisherWindow(user_obj, self.db_config)
        self.pub_win.show()
        
    def openAdminWindow(self, user_obj):
        self.hide()
        self.admin_win = AdminWindow(user_obj, self.db_config)
        self.admin_win.show()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())