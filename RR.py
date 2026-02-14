import sys
import os
import ctypes
import pyodbc
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox, QLineEdit, QMainWindow, QVBoxLayout, QLabel, QPushButton, QFrame, QApplication

# IMPORT LOGIN WINDOW
from Login import LoginWindow

# --- 1. FIX TASKBAR ICON ---
# This makes the icon show up in the bottom taskbar, not just the window corner
try:
    myappid = 'retro.reload.store.v1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

# --- 2. DEFINE RESOURCE PATH FUNCTION ---
# This allows the app to find images even when converted to .EXE
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # IN DEVELOPMENT: Use the folder where this python file is located
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class StartupWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Retro Reload - Server Connection")
        self.resize(400, 550)
        self.setStyleSheet("background-color: #2c3e50;")
        
        # --- 3. SET ICON CORRECTLY ---
        # Make sure "Icon.png" is in the same folder as this script
        self.setWindowIcon(QtGui.QIcon(resource_path("Icon.png")))
        
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(20)
        
        # Header
        lbl_title = QLabel("SERVER SETUP")
        lbl_title.setAlignment(QtCore.Qt.AlignCenter)
        lbl_title.setStyleSheet("color: white; font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        self.layout.addWidget(lbl_title)
        
        # Inputs
        self.inp_ip = self.createInput("IP Address", "127.0.0.1") # Localhost default
        self.inp_port = self.createInput("Port Number", "1433")   # Standard SQL Port
        self.inp_user = self.createInput("SQL Username", "RETRO_RELOAD_ADMIN")
        self.inp_pass = self.createInput("SQL Password", "RetroReload123*", is_password=True)
        
        # Connect Button
        self.btn_connect = QPushButton("CONNECT TO DATABASE")
        self.btn_connect.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_connect.setStyleSheet("""
            QPushButton { 
                background-color: #27ae60; color: white; font-weight: bold; 
                padding: 15px; border-radius: 8px; font-size: 14px; margin-top: 20px; 
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_connect.clicked.connect(self.attemptConnection)
        self.layout.addWidget(self.btn_connect)
        
        self.layout.addStretch()

    def createInput(self, placeholder, default_val="", is_password=False):
        lbl = QLabel(placeholder)
        lbl.setStyleSheet("color: #ecf0f1; font-size: 12px; font-weight: bold;")
        self.layout.addWidget(lbl)
        
        inp = QLineEdit()
        inp.setText(default_val)
        if is_password: inp.setEchoMode(QLineEdit.Password)
        inp.setStyleSheet("""
            QLineEdit {
                padding: 12px; border-radius: 6px; border: 2px solid #34495e; 
                background-color: white; color: #2c3e50; font-size: 14px;
            }
            QLineEdit:focus { border: 2px solid #3498db; }
        """)
        self.layout.addWidget(inp)
        return inp

    def attemptConnection(self):
        ip = r'CHUZA\SQLEXPRESS'
        port = self.inp_port.text().strip()
        user = self.inp_user.text().strip()
        pwd = self.inp_pass.text().strip()
        
        if not all([ip, port, user, pwd]):
            QMessageBox.warning(self, "Error", "All fields are required.")
            return
            
        # TCP/IP Connection String
        conn_str = f'Driver={{ODBC Driver 18 for SQL Server}};Server={ip},{port};Database=RETRO_RELOAD;UID={user};PWD={pwd};Encrypt=no;TrustServerCertificate=yes;'
        
        self.btn_connect.setText("CONNECTING...")
        self.btn_connect.setEnabled(False)
        QApplication.processEvents()
        
        try:
            # Attempt Connection
            conn = pyodbc.connect(conn_str, timeout=5)
            conn.close()
            db_config = {
                "server": ip,
                "port": port,
                "uid": user,
                "pwd": pwd
            }
            self.login_win = LoginWindow(db_config)
            self.login_win.show()
            self.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to database at {ip}:{port}.\n\nCheck if the server is running and accessible.\n\nError: {e}")
            self.btn_connect.setText("CONNECT TO DATABASE")
            self.btn_connect.setEnabled(True)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = StartupWindow()
    window.show()
    sys.exit(app.exec_())