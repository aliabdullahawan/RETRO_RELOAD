import sys
import os  # REQUIRED FOR PATH FINDING
import datetime
import random
import re
import pyodbc
import csv
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QScrollArea, QLineEdit, QComboBox, QTextEdit, QGridLayout, QDialog

# --- IMPORT THEME MANAGER ---
try:
    from GIMINI_Styles import ThemeManager
except ImportError:
    ThemeManager = None

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

# --- DATABASE MANAGER ---
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

    def get_user_id_by_email(self, email):
        conn = self.get_connection()
        if not conn: return None
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_FindUserIDByEmail ?", (email,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"ID Fetch Error: {e}")
            return None
        finally: conn.close()

    def fetch_publisher_info(self, user_id):
        conn = self.get_connection()
        if not conn: return None
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetUserInfo ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "fname": row.User_fname, "lname": row.User_Lname,
                    "username": row.User_username, "email": row.User_Email,
                    "pfp_data": row.User_ProfilePic, "balance": float(row.Wallet_Balance),
                    "password": getattr(row, 'User_Password', ''),
                    "card": getattr(row, 'Card_Number', '')
                }
            return None
        finally: conn.close()

    def update_profile_pic(self, user_id, image_bytes):
        conn = self.get_connection() 
        if not conn: return False
        try:
            binary_data = pyodbc.Binary(image_bytes)
            conn.cursor().execute("EXEC sp_UpdateUserProfilePic ?, ?", (user_id, binary_data))
            conn.commit()
            return True
        except Exception as e:
            print(f"Image Upload Error: {e}")
            return False
        finally: conn.close()

    def update_profile_text(self, uid, f, l, u, e, p, c):
        conn = self.get_connection() 
        if not conn: return False
        try:
            conn.cursor().execute("EXEC sp_UpdateUserProfile ?, ?, ?, ?, ?, ?, ?", (uid, f, l, u, e, p, c))
            conn.commit(); return True
        except: return False
        finally: conn.close()

    def fetch_publisher_stats(self, pub_id):
        conn = self.get_connection() 
        if not conn: return (0,0,0)
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetPublisherStats ?", (pub_id,))
            row = cursor.fetchone()
            return row if row else (0,0,0)
        finally: conn.close()

    def withdraw_funds(self, pub_id, amount):
        conn = self.get_connection() 
        if not conn: return False
        try:
            conn.cursor().execute("EXEC sp_WithdrawFunds ?, ?", (pub_id, amount))
            conn.commit(); return True
        except: return False
        finally: conn.close()

    def fetch_recent_sales(self, pub_id):
        conn = self.get_connection() 
        if not conn: return []
        data = []
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetPublisherRecentSales ?", (pub_id,))
            for r in cursor.fetchall(): data.append(r)
        except: pass
        finally: conn.close()
        return data

    def fetch_recent_reviews(self, pub_id):
        conn = self.get_connection() 
        if not conn: return []
        data = []
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetPublisherRecentReviews ?", (pub_id,))
            for r in cursor.fetchall(): data.append(r)
        except: pass
        finally: conn.close()
        return data

    def fetch_publisher_games(self, pub_id):
        conn = self.get_connection() 
        if not conn: return {}
        games = {}
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetPublisherGames ?", (pub_id,))
            rows = cursor.fetchall()
            for row in rows:
                units = getattr(row, 'Units_Sold', 0)
                
                # --- UNIVERSAL IMAGE FETCH ---
                img_data = getattr(row, 'Game_Image', None)
                if not img_data: img_data = getattr(row, 'Game_Icon', None)
                
                games[row.Game_ID] = {
                    "title": row.Game_name, 
                    "price": float(row.Game_Price),
                    "genre": row.Game_Genre, 
                    "sold": units,
                    "size": f"{row.Game_Size} GB", 
                    "downloads": str(units),
                    "desc": row.Game_Description,
                    "image": img_data 
                }
        except Exception as e:
            print(f"DB Error Fetching Games: {e}")
        finally: conn.close()
        return games
    
    def upload_game(self, pub_id, title, genre, price, size, desc, img_data, file_data):
        conn = self.get_connection() 
        if not conn: return False
        try:
            img_blob = pyodbc.Binary(img_data)
            file_blob = pyodbc.Binary(file_data)
            conn.cursor().execute("EXEC sp_UploadGame ?, ?, ?, ?, ?, ?, ?, ?", (pub_id, title, genre, price, size, desc, img_blob, file_blob))
            conn.commit(); return True
        except: return False
        finally: conn.close()

    def edit_game(self, gid, t, p, d):
        conn = self.get_connection() 
        if not conn: return False
        try:
            conn.cursor().execute("EXEC sp_EditGame ?, ?, ?, ?", (gid, t, p, d))
            conn.commit(); return True
        except: return False
        finally: conn.close()
    
    def delete_game(self, gid):
        conn = self.get_connection() 
        if not conn: return False
        try:
            conn.cursor().execute("EXEC sp_DeleteGame ?", (gid,))
            conn.commit(); return True
        except: return False
        finally: conn.close()

    def fetch_sales_report(self, pub_id):
        conn = self.get_connection() 
        if not conn: return []
        data = []
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetPublisherSales ?", (pub_id,))
            for row in cursor.fetchall():
                # FIX: Changed 'row.Sold_Count' to 'row.Units_Sold' to match SQL View
                data.append({
                    "title": row.Game_name, 
                    "price": float(row.Game_Price), 
                    "sold": row.Units_Sold, # <--- THIS WAS THE ERROR
                    "revenue": float(row.Revenue)
                })
        except Exception as e:
            print(f"Sales Report Error: {e}") # Added print to help debug in future
        finally: conn.close()
        return data

    def fetch_game_reviews(self, gid):
        conn = self.get_connection() 
        if not conn: return []
        reviews = []
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetReviewsByGame ?", (gid,))
            for row in cursor.fetchall(): 
                reviews.append((row.Review_ID, row.Reviewer, row.Review_Text, row.Rating))
        finally: conn.close()
        return reviews

    def delete_review(self, rid):
        conn = self.get_connection() 
        if not conn: return False
        try:
            conn.cursor().execute("EXEC sp_DeleteReview ?", (rid,))
            conn.commit(); return True
        except: return False
        finally: conn.close()

    def fetch_community_feed(self):
        conn = self.get_connection() 
        if not conn: return []
        posts = []
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetCommunityFeed")
            for row in cursor.fetchall():
                posts.append({"id": row.Com_ID, "user": row.Username, "role": row.User_Role, "text": row.Comment, "date": str(row.Comment_Date)})
        finally: conn.close()
        return posts
        
    def fetch_my_comments(self, uid):
        conn = self.get_connection() 
        if not conn: return []
        posts = []
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetUserComments ?", (uid,))
            for row in cursor.fetchall():
                posts.append({"id": row.Com_ID, "text": row.Comment, "date": str(row.Comment_Date)})
        finally: conn.close()
        return posts

    def add_community_post(self, uid, txt):
        conn = self.get_connection() 
        if not conn: return
        try: conn.cursor().execute("EXEC sp_AddCommunityPost ?, ?", (uid, txt)); conn.commit()
        finally: conn.close()

    def delete_post(self, pid):
        conn = self.get_connection() 
        if not conn: return False
        try: conn.cursor().execute("EXEC sp_DeletePost ?", (pid,)); conn.commit(); return True
        except: return False
        finally: conn.close()
            
    def logout_user(self, user_id):
        conn = self.get_connection() 
        if not conn: return
        try: conn.cursor().execute("EXEC sp_UserLogout ?", (user_id,)); conn.commit()
        except: pass
        finally: conn.close()

# --- Main Window Class ---
class PublisherWindow(QtWidgets.QMainWindow):
    def __init__(self, user_data=None, db_config=None):
        super().__init__()
        # INITIALIZE VARIABLES FIRST
        self.games_db = {}
        self.user_full_info = {}
        self.user_db_id = None
        self.email = ""
        self.publisher_name = "Loading..."
        self.fname = ""
        self.lname = ""
        self.is_verified = False
        self.revenue_total = 0.0
        self.withdrawable_balance = 0.0
        
        self.sales_layout_container = None
        self.reviews_layout_container = None

        self.ui = Ui_PublisherWindow()
        self.db = DatabaseManager(db_config)
        
        # --- 1. DETERMINE USER ID ---
        if user_data:
            self.user_db_id = user_data.id
            self.email = user_data.email
            print(f"Login Detected: ID {self.user_db_id}")
        else:
            self.email = "awan.ali.abdullah@gmail.com" 
            print(f"Standalone Mode: Using ID for {self.email}")
            self.user_db_id = self.db.get_user_id_by_email(self.email)

        if not self.user_db_id:
            print("ERROR: User ID is None. Data cannot load.")
        
        # Setup UI
        self.ui.setupUi(self, self.publisher_name, self.is_verified, 0.0)
        self.setWindowTitle(f"Retro Reload - Publisher Studio (ID: {self.user_db_id})") 
        
        # --- FIX: USE RESOURCE PATH FOR ICON ---
        self.setWindowIcon(QtGui.QIcon(resource_path('Icon.png')))
        
        # --- 2. FETCH FULL DATA ---
        if self.user_db_id:
            self.refreshAllData()
        
        self.setup_connections()

    def refreshAllData(self):
        try:
            print(f"Refreshing Data for ID: {self.user_db_id}")
            
            # 1. Fetch Personal Info
            info = self.db.fetch_publisher_info(self.user_db_id)
            if info:
                self.user_full_info = info 
                self.fname = info['fname']
                self.lname = info['lname']
                self.email = info['email']
                self.publisher_name = info['username']
                self.withdrawable_balance = info['balance']
                self.is_verified = True
                
                self.ui.lbl_name_profile.setText(f"{self.fname} {self.lname}")
                self.ui.lbl_user_profile.setText(f"@{self.publisher_name}")
                self.ui.lbl_email_profile.setText(self.email)
                self.ui.lbl_balance.setText(f"Balance: ${self.withdrawable_balance:,.2f}")
                self.ui.lbl_welcome.setText(f"Welcome back, {self.publisher_name}!") 

                if info['pfp_data']:
                    pixmap = QtGui.QPixmap()
                    if pixmap.loadFromData(info['pfp_data']):
                        self.ui.lbl_pfp.setPixmap(pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation))
                        self.ui.lbl_pfp.setText("")
                else:
                    initial = self.fname[0].upper() if self.fname else "?"
                    self.ui.lbl_pfp.setText(initial)

            # 2. Stats & Games
            stats = self.db.fetch_publisher_stats(self.user_db_id)
            self.revenue_total = float(stats[0]) 
            self.ui.updateDashboardStats(self.revenue_total, self.revenue_total * 0.7, int(stats[1]), float(stats[2]))
            
            recent_sales = self.db.fetch_recent_sales(self.user_db_id)
            recent_reviews = self.db.fetch_recent_reviews(self.user_db_id)
            self.ui.updateDashboardLists(recent_sales, recent_reviews)
            
            # FETCH GAMES
            self.games_db = self.db.fetch_publisher_games(self.user_db_id)
            print(f"Found {len(self.games_db)} games.")
            self.ui.refreshMyGames(self.games_db)
            
            # 3. Comments & History
            my_comments = self.db.fetch_my_comments(self.user_db_id)
            self.ui.btn_sold_profile.setText(f"{len(self.games_db)}\nTotal Games")
            self.ui.btn_comm_profile.setText(f"{len(my_comments)}\nComments")
            
            self.loadHistoryList(my_comments)
            self.loadCommunityFeed()
            
        except Exception as e:
            print(f"Data Load Error: {e}")
            QMessageBox.critical(self, "Data Load Error", f"Failed to load publisher data:\n{e}")

    def setup_connections(self):
        self.ui.btn_dashboard.clicked.connect(lambda: self.ui.stack.setCurrentIndex(0))
        self.ui.btn_mygames.clicked.connect(lambda: self.ui.stack.setCurrentIndex(1))
        self.ui.btn_upload.clicked.connect(lambda: self.ui.stack.setCurrentIndex(2))
        self.ui.btn_analytics.clicked.connect(lambda: self.ui.stack.setCurrentIndex(3))
        self.ui.btn_community.clicked.connect(lambda: self.ui.stack.setCurrentIndex(5))
        self.ui.btn_profile.clicked.connect(lambda: self.ui.stack.setCurrentIndex(4))
        self.ui.btn_logout.clicked.connect(self.logoutFunc)
        
        self.ui.btn_browse_pic.clicked.connect(self.browsePicture)
        self.ui.btn_browse_file.clicked.connect(self.browseGameFile)
        self.ui.btn_publish.clicked.connect(self.publishGameFunc)
        self.ui.btn_add_genre.clicked.connect(self.addCustomGenre)
        
        self.ui.btn_view_sales.clicked.connect(self.openSalesPage)
        self.ui.btn_export_excel.clicked.connect(self.exportToExcel)
        self.ui.btn_back_analytics.clicked.connect(lambda: self.ui.stack.setCurrentIndex(3))
        
        self.ui.editProfile_btn.clicked.connect(self.openEditProfileDialog)
        self.ui.transfer_btn.clicked.connect(self.transferMoneyFunc)
        
        self.ui.button_addComment.clicked.connect(self.postCommunityComment)
        self.ui.btn_back_history.clicked.connect(lambda: self.ui.stack.setCurrentIndex(4))
        self.ui.btn_back_viewPage.clicked.connect(lambda: self.ui.stack.setCurrentIndex(1))
        
        self.ui.btn_sold_profile.clicked.connect(lambda: self.ui.stack.setCurrentIndex(1))
        self.ui.btn_comm_profile.clicked.connect(lambda: self.ui.stack.setCurrentIndex(6))

    def exportToExcel(self):
        try:
            sales_data = self.db.fetch_sales_report(self.user_db_id)
            if not sales_data:
                QMessageBox.information(self, "Export", "No sales data available to export.")
                return

            fname, _ = QFileDialog.getSaveFileName(self, "Export Data", "", "CSV Files (*.csv)")
            if fname:
                with open(fname, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Retro Reload - Publisher Report"])
                    writer.writerow([f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                    writer.writerow([f"Publisher: {self.publisher_name}"])
                    writer.writerow([]) 
                    writer.writerow(["--- Overall Statistics ---"])
                    writer.writerow(["Total Revenue", f"${self.revenue_total:.2f}"])
                    writer.writerow(["Withdrawable Balance", f"${self.withdrawable_balance:.2f}"])
                    writer.writerow([])
                    writer.writerow(["--- Sales by Game ---"])
                    writer.writerow(["Game Title", "Unit Price", "Units Sold", "Total Revenue"])
                    for item in sales_data:
                        writer.writerow([
                            item['title'], 
                            f"${item['price']:.2f}", 
                            item['sold'], 
                            f"${item['revenue']:.2f}"
                        ])
                QMessageBox.information(self, "Success", "Data exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data: {e}")

    # --- PFP LOGIC ---
    def changeProfilePicture(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select Profile Picture', 'c:\\', "Image files (*.png *.jpg)")
        if fname:
            with open(fname, 'rb') as f:
                binary_data = f.read()
            if self.db.update_profile_pic(self.user_db_id, binary_data):
                self.refreshAllData()
                QMessageBox.information(self, "Success", "Profile picture updated!")
            else:
                QMessageBox.warning(self, "Error", "Failed to save image.")

    def openEditProfileDialog(self):
        d = QDialog(self); d.setWindowTitle("Edit Profile"); d.setFixedSize(300, 500); l = QVBoxLayout(d)
        btn_pic = QPushButton("Change Profile Picture"); btn_pic.setStyleSheet("background-color: #34495e; color: white; padding: 8px;")
        btn_pic.clicked.connect(self.changeProfilePicture); l.addWidget(btn_pic)
        
        def add_f(lbl, val, is_pass=False):
            l.addWidget(QLabel(lbl)); 
            le = QLineEdit(str(val) if val else "")
            if is_pass: le.setEchoMode(QLineEdit.Password)
            l.addWidget(le); return le

        ef = add_f("First Name:", self.user_full_info.get('fname'))
        el = add_f("Last Name:", self.user_full_info.get('lname'))
        eu = add_f("Username:", self.user_full_info.get('username'))
        ee = add_f("Email:", self.user_full_info.get('email'))
        
        # PRE-FILLED PASSWORD AND CARD
        ep = add_f("Password:", self.user_full_info.get('password'), True)
        ec = add_f("Card Number:", self.user_full_info.get('card'))

        btn = QPushButton("Save Changes"); l.addWidget(btn)
        btn.clicked.connect(lambda: self.saveProfile(d, ef.text(), el.text(), eu.text(), ee.text(), ep.text(), ec.text()))
        d.exec_()
        
    def saveProfile(self, d, f, l, u, e, p, c):
        if self.db.update_profile_text(self.user_db_id, f, l, u, e, p, c):
            self.refreshAllData(); d.accept(); QMessageBox.information(self, "Success", "Profile Updated")

    def openPublisherGameView(self, game_id):
        if game_id not in self.games_db: return
        data = self.games_db[game_id]
        self.ui.pv_title.setText(data['title'])
        self.ui.pv_price.setText(f"${data['price']}")
        self.ui.pv_publisher.setText(f"Publisher: {self.publisher_name}")
        self.ui.pv_genre.setText(f"Genre: {data['genre']}")
        self.ui.pv_size.setText(f"Size: {data['size']}")
        self.ui.pv_downloads.setText(f"{data['downloads']} Downloads")
        
        # --- FIX: Set Description (Will be auto-wrapped) ---
        self.ui.pv_desc.setText(data['desc'])
        
        if data.get('image'):
            pix = QtGui.QPixmap()
            if pix.loadFromData(data['image']):
                self.ui.pv_image.setPixmap(pix.scaled(300, 400, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                self.ui.pv_image.setText("")
            else:
                self.ui.pv_image.setText(data['title'])
        else:
            self.ui.pv_image.setText(data['title'])
        
        try:
            self.ui.pv_btn_edit.clicked.disconnect()
        except:
            pass
        try:
            self.ui.pv_btn_del.clicked.disconnect()
        except:
            pass
        
        self.ui.pv_btn_edit.clicked.connect(lambda: self.editGameFunc(game_id))
        self.ui.pv_btn_del.clicked.connect(lambda: self.deleteGameFunc(game_id))
        
        self.refreshGameReviews(game_id)
        self.ui.stack.setCurrentIndex(8)

    def refreshGameReviews(self, game_id):
        self.ui.clearLayout(self.ui.pv_reviews_layout)
        reviews = self.db.fetch_game_reviews(game_id)
        if not reviews:
            self.ui.pv_reviews_layout.addWidget(QLabel("No reviews yet."))
        for r_id, user, text, rating in reviews:
            self.ui.pv_reviews_layout.addWidget(self.createReviewCard(r_id, user, text, rating, game_id))

    def createReviewCard(self, rid, user, review, rating, gid):
        c = QFrame(); c.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 5px;")
        l = QHBoxLayout(c)
        v = QVBoxLayout(); 
        v.addWidget(QLabel(f"<b>{user}</b> ({rating}★)"))
        
        # --- CRITICAL FIX FOR STRETCHING ---
        lbl_text = QLabel(review)
        lbl_text.setStyleSheet("color:#555")
        lbl_text.setWordWrap(True)
        # FORCE width constraint: Ignored means "shrink to fit container"
        lbl_text.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        v.addWidget(lbl_text)
        
        l.addLayout(v)
        btn = QPushButton("Delete"); btn.setFixedWidth(60); btn.setStyleSheet("background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;")
        btn.clicked.connect(lambda: self.deleteReviewFunc(rid, gid)); l.addWidget(btn); return c

    def deleteReviewFunc(self, rid, gid):
        if QMessageBox.question(self, "Delete", "Delete this review?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_review(rid):
                self.refreshGameReviews(gid)
                QMessageBox.information(self, "Success", "Review deleted.")

    def browsePicture(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select Game Image', 'c:\\', "Image files (*.jpg *.png)")
        if fname: self.ui.lbl_pic_path.setText(fname)

    def browseGameFile(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select Game File', 'c:\\', "Game files (*.exe *.zip *.rar)")
        if fname: self.ui.lbl_file_path.setText(fname)

    def addCustomGenre(self):
        new_genre = self.ui.input_new_genre.text().strip()
        if new_genre:
            self.ui.input_genre.addItem(new_genre); self.ui.input_genre.setCurrentText(new_genre); self.ui.input_new_genre.clear()

    def publishGameFunc(self):
        title = self.ui.input_title.text(); price_txt = self.ui.input_price.text(); size_txt = self.ui.input_size.text()
        desc = self.ui.input_desc.toPlainText(); genre = self.ui.input_genre.currentText()
        img_path = self.ui.lbl_pic_path.text(); file_path = self.ui.lbl_file_path.text()

        if not all([title, price_txt, size_txt, desc, img_path, file_path]): 
            QMessageBox.warning(self, "Error", "Fill all fields and select files")
            return
        try:
            price = float(price_txt); size = int(re.sub("[^0-9]", "", size_txt))
        except:
            QMessageBox.warning(self, "Error", "Price/Size must be numbers")
            return

        try:
            with open(img_path, 'rb') as f: img_data = f.read()
            with open(file_path, 'rb') as f: file_data = f.read()
            
            if self.db.upload_game(self.user_db_id, title, genre, price, size, desc, img_data, file_data):
                QMessageBox.information(self, "Success", "Game Published!")
                self.refreshAllData()
            else:
                QMessageBox.critical(self, "Error", "Upload Failed")
        except Exception as e:
            QMessageBox.critical(self, "File Error", str(e))

    def editGameFunc(self, game_id):
        game = self.games_db.get(game_id)
        if not game: return
        d = QDialog(self); d.setWindowTitle("Edit"); d.setFixedSize(300, 400); l = QVBoxLayout(d)
        l.addWidget(QLabel("Title")); it = QLineEdit(game['title']); l.addWidget(it)
        l.addWidget(QLabel("Price")); ip = QLineEdit(str(game['price'])); l.addWidget(ip)
        l.addWidget(QLabel("Desc")); ide = QTextEdit(game['desc']); ide.setMaximumHeight(80); l.addWidget(ide)
        btn = QPushButton("Save"); l.addWidget(btn)
        
        def save():
            if self.db.edit_game(game_id, it.text(), float(ip.text()), ide.toPlainText()):
                self.refreshAllData(); d.accept(); QMessageBox.information(self, "Success", "Updated")
        btn.clicked.connect(save); d.exec_()

    def deleteGameFunc(self, game_id):
        if QMessageBox.question(self, 'Delete', "Delete Game?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_game(game_id):
                self.refreshAllData(); self.ui.stack.setCurrentIndex(1)

    def transferMoneyFunc(self):
        if self.withdrawable_balance <= 0: 
            QMessageBox.warning(self, "Error", "No funds.")
            return
        if QMessageBox.question(self, "Transfer", f"Withdraw ${self.withdrawable_balance:.2f}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.db.withdraw_funds(self.user_db_id, self.withdrawable_balance):
                self.refreshAllData(); QMessageBox.information(self, "Success", "Funds Withdrawn.")
            else:
                QMessageBox.critical(self, "Error", "Withdrawal Failed.")

    def openSalesPage(self):
        self.ui.clearLayout(self.ui.sales_layout)
        h = QHBoxLayout()
        h.addWidget(QLabel("Game", styleSheet="font-weight:bold"))
        h.addWidget(QLabel("Price", styleSheet="font-weight:bold"))
        h.addWidget(QLabel("Sold", styleSheet="font-weight:bold"))
        h.addWidget(QLabel("Revenue", styleSheet="font-weight:bold"))
        self.ui.sales_layout.addLayout(h)
        
        sales_data = self.db.fetch_sales_report(self.user_db_id)
        if not sales_data:
            self.ui.sales_layout.addWidget(QLabel("No sales yet."))
        else:
            for item in sales_data:
                r = QHBoxLayout()
                r.addWidget(QLabel(item['title']))
                r.addWidget(QLabel(f"${item['price']:.2f}"))
                r.addWidget(QLabel(str(item['sold'])))
                r.addWidget(QLabel(f"${item['revenue']:.2f}", styleSheet="color:green; font-weight:bold"))
                f = QFrame(); f.setStyleSheet("background-color:white; border-bottom:1px solid #eee; padding:5px;"); f.setLayout(r)
                self.ui.sales_layout.addWidget(f)
        self.ui.stack.setCurrentIndex(7)

    def postCommunityComment(self):
        t = self.ui.addText_community.toPlainText().strip()
        if t:
            self.db.add_community_post(self.user_db_id, t)
            self.refreshAllData()
            self.ui.addText_community.clear()

    def loadCommunityFeed(self):
        self.ui.clearLayout(self.ui.community_layout)
        for p in self.db.fetch_community_feed():
            self.ui.community_layout.addWidget(self.createCommentCard(p))

    def createCommentCard(self, p):
        c = QFrame(); c.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 5px;")
        l = QHBoxLayout(c)
        bg = "#e67e22" if p['role']=='Publisher' else ("#c0392b" if p['role']=='Admin' else "#3498db")
        
        lbl = QLabel(p['user'][0])
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setFixedSize(40,40)
        lbl.setStyleSheet(f"background-color:{bg}; color:white; border-radius:20px;")
        l.addWidget(lbl)
        
        v = QVBoxLayout(); v.addWidget(QLabel(f"<b>{p['user']}</b> <span style='color:gray; font-size:10px;'>{p['date']}</span>"))
        
        # --- FIX: FORCE WRAP FOR POSTS ---
        lbl_text = QLabel(p['text'])
        lbl_text.setWordWrap(True)
        lbl_text.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        v.addWidget(lbl_text)
        
        l.addLayout(v)
        btn = QPushButton("Del"); btn.setFixedWidth(40); btn.setStyleSheet("background-color: #c0392b; color: white; border-radius: 5px;")
        btn.clicked.connect(lambda: self.deletePostFunc(p['id'])); l.addWidget(btn); return c

    def deletePostFunc(self, pid):
        if QMessageBox.question(self, "Delete", "Delete this post?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_post(pid):
                self.refreshAllData(); QMessageBox.information(self, "Success", "Post deleted.")

    def loadHistoryList(self, comments):
        self.ui.clearLayout(self.ui.history_layout)
        if not comments: 
            self.ui.history_layout.addWidget(QLabel("No comment history."))
        for c in comments:
            self.ui.history_layout.addWidget(self.createHistoryCard(c))

    def createHistoryCard(self, c):
        f = QFrame(); f.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 5px;")
        l = QHBoxLayout(f)
        v = QVBoxLayout(); v.addWidget(QLabel(f"<b>{c['date']}</b>"))
        
        # --- FIX: FORCE WRAP FOR HISTORY ---
        lbl_text = QLabel(c['text'])
        lbl_text.setStyleSheet("color: #555;")
        lbl_text.setWordWrap(True)
        lbl_text.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        v.addWidget(lbl_text)
        
        l.addLayout(v)
        btn = QPushButton("Delete"); btn.setFixedWidth(60); btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; border-radius: 5px;")
        btn.clicked.connect(lambda: self.deleteHistoryItem(c['id']))
        l.addWidget(btn)
        return f
        
    def deleteHistoryItem(self, pid):
        if QMessageBox.question(self, "Delete", "Delete comment?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_post(pid):
                self.refreshAllData()
                QMessageBox.information(self, "Success", "Deleted.")

    def logoutFunc(self): 
        if QMessageBox.question(self, "Logout", "Logout?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes: 
            self.db.logout_user(self.user_db_id)
            QtWidgets.QApplication.quit()
    
    # Close event to ensure status update on X button
    def closeEvent(self, event):
        self.db.logout_user(self.user_db_id)
        event.accept()

# --- UI Class ---
class Ui_PublisherWindow(object):
    def setupUi(self, MainWindow, name, verified, revenue):
        self.mainWindow = MainWindow; self.pubName = name
        MainWindow.setObjectName("MainWindow"); MainWindow.resize(1200, 720); MainWindow.setStyleSheet("QMainWindow { background-color: #f0f2f5; }")
        self.centralwidget = QtWidgets.QWidget(MainWindow); self.createSidebar(self.centralwidget); self.createStack(self.centralwidget)
        self.createDashboard(name, verified, revenue); self.createMyGamesPage(MainWindow.games_db); self.createUploadPage(); self.createAnalyticsPage(); self.createProfilePage(MainWindow); self.createCommunityPage(MainWindow.publisher_name); self.createCommentHistoryPage(); self.createGameSalesPage(MainWindow.games_db); self.createPublisherGameViewPage()
        MainWindow.setCentralWidget(self.centralwidget); self.stack.setCurrentIndex(0)

    def createSidebar(self, parent):
        self.frame = QFrame(parent); self.frame.setGeometry(0, 0, 180, 720); self.frame.setStyleSheet("background-color: white; border-right: 1px solid #dcdcdc;")
        l = QVBoxLayout(self.frame); l.setSpacing(10); l.setContentsMargins(10, 20, 10, 20)
        l.addWidget(QLabel("RETRO\nRELOAD", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 20px;"))
        self.btn_dashboard = self.navBtn("DASHBOARD"); l.addWidget(self.btn_dashboard)
        self.btn_mygames = self.navBtn("MY GAMES"); l.addWidget(self.btn_mygames)
        self.btn_upload = self.navBtn("UPLOAD GAME"); l.addWidget(self.btn_upload)
        self.btn_analytics = self.navBtn("ANALYTICS"); l.addWidget(self.btn_analytics)
        self.btn_community = self.navBtn("COMMUNITY"); l.addWidget(self.btn_community)
        self.btn_profile = self.navBtn("PROFILE"); l.addWidget(self.btn_profile)
        l.addStretch(); self.btn_logout = self.navBtn("LOGOUT"); l.addWidget(self.btn_logout)

    def navBtn(self, text):
        btn = QPushButton(text); btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor)); btn.setStyleSheet("QPushButton { border: none; text-align: left; padding: 12px; color: #555; font-weight: bold; } QPushButton:hover { background-color: #f0f2f5; color: #2980b9; border-radius: 5px; }"); return btn
    def createStack(self, parent): self.stack = QtWidgets.QStackedWidget(parent); self.stack.setGeometry(151, 0, 1019, 720)

    def createMyGamesPage(self, games_db):
        self.MyGamesPage = QWidget(); l = QVBoxLayout(self.MyGamesPage); l.setContentsMargins(30,30,30,30)
        l.addWidget(QLabel("Manage Your Catalog", styleSheet="font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;"))
        s = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); w = QWidget(); self.myGamesGrid = QGridLayout(w); self.myGamesGrid.setSpacing(20)
        self.refreshMyGames(games_db)
        s.setWidget(w); l.addWidget(s); self.stack.addWidget(self.MyGamesPage)

    def refreshMyGames(self, games_db):
        self.clearLayout(self.myGamesGrid)
        idx = 0
        for gid, data in games_db.items():
            self.myGamesGrid.addWidget(self.manageGameCard(self.mainWindow, gid, data), idx//4, idx%4); idx += 1

    def manageGameCard(self, MainRef, gid, data):
        f = QFrame(); f.setFixedSize(200, 280); f.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd;")
        l = QVBoxLayout(f); l.setContentsMargins(10,10,10,10); l.setSpacing(5)
        
        # --- FIX: Show Image if available ---
        img_label = QLabel()
        img_label.setAlignment(QtCore.Qt.AlignCenter)
        img_label.setStyleSheet("background-color: #ecf0f1; border-radius: 5px; min-height: 100px;")
        
        if data.get('image'):
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(data['image']):
                img_label.setPixmap(pixmap.scaled(180, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            else:
                img_label.setText(f"IMG {gid}")
        else:
            img_label.setText(f"IMG {gid}")
            
        l.addWidget(img_label)
        
        l.addWidget(QLabel(data['title'], styleSheet="font-weight: bold; font-size: 12px;"))
        l.addWidget(QLabel(f"{data['genre']}\n${data['price']}", styleSheet="color: #7f8c8d; font-size: 10px;"))
        btn_view = QPushButton("View Page"); btn_view.setStyleSheet("background-color: #2980b9; color: white; border-radius: 4px; padding: 4px; font-size:11px;")
        btn_view.clicked.connect(lambda: MainRef.openPublisherGameView(gid)); l.addWidget(btn_view)
        row = QHBoxLayout(); btn_edit = QPushButton("Edit"); btn_edit.setStyleSheet("background-color: #f39c12; color: white; border-radius: 4px; padding: 4px; font-size:11px;")
        btn_del = QPushButton("Delete"); btn_del.setStyleSheet("background-color: #e74c3c; color: white; border-radius: 4px; padding: 4px; font-size:11px;")
        btn_edit.clicked.connect(lambda: MainRef.editGameFunc(gid)); btn_del.clicked.connect(lambda: MainRef.deleteGameFunc(gid))
        row.addWidget(btn_edit); row.addWidget(btn_del); l.addLayout(row); return f

    def clearLayout(self, layout):
        while layout.count(): item = layout.takeAt(0); item.widget().deleteLater()

    # --- DASHBOARD & OTHER PAGES ---
    def createDashboard(self, name, verified, revenue):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(40,40,40,40); l.setSpacing(20)
        self.lbl_welcome = QLabel(f"Welcome back, {name}!", styleSheet="font-size: 28px; font-weight: bold; color: #2c3e50;")
        l.addWidget(self.lbl_welcome)
        
        # Stats Cards
        row = QHBoxLayout()
        self.card_rev = self.statCard("Total Revenue", f"${revenue:,.2f}", "#2980b9")
        self.card_prof = self.statCard("Profit (70%)", f"${revenue*0.7:,.2f}", "#27ae60")
        self.card_dl = self.statCard("Total Downloads", "0", "#8e44ad")
        self.card_rate = self.statCard("Avg Rating", "0.0", "#f39c12")
        
        row.addWidget(self.card_rev); row.addWidget(self.card_prof); row.addWidget(self.card_dl); row.addWidget(self.card_rate)
        l.addLayout(row)
        
        # Lists
        split = QHBoxLayout()
        
        box_sales, self.sales_layout_container = self.createScrollBox("Recent Sales")
        box_reviews, self.reviews_layout_container = self.createScrollBox("Recent Reviews")
        
        split.addWidget(box_sales)
        split.addWidget(box_reviews)
        l.addLayout(split)
        
        self.stack.addWidget(p)

    def updateDashboardStats(self, r, p, d, rt):
        # Helper to update cards dynamically
        self.card_rev.layout().itemAt(1).widget().setText(f"${r:,.2f}")
        self.card_prof.layout().itemAt(1).widget().setText(f"${p:,.2f}")
        self.card_dl.layout().itemAt(1).widget().setText(str(d))
        self.card_rate.layout().itemAt(1).widget().setText(f"{rt:.1f} ★")

    def updateDashboardLists(self, sales, reviews):
        # FIX: Directly use the layout containers saved earlier
        self.clearLayout(self.sales_layout_container)
        for g, u, a, d in sales:
             # --- FIX: WORD WRAP FOR DASHBOARD ---
             l = QLabel(f"{u} bought {g} (${a:,.2f})")
             l.setWordWrap(True)
             l.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
             l.setStyleSheet("border-bottom:1px solid #eee; padding:5px; color:#555")
             self.sales_layout_container.addWidget(l)

        self.clearLayout(self.reviews_layout_container)
        for g, u, r, t, d in reviews:
             # --- FIX: WORD WRAP FOR DASHBOARD REVIEWS ---
             l = QLabel(f"{u}: {t} ({r}★)")
             l.setWordWrap(True)
             l.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
             l.setStyleSheet("border-bottom:1px solid #eee; padding:5px; color:#555")
             self.reviews_layout_container.addWidget(l)

    def statCard(self, t, v, c):
        f = QFrame(); f.setStyleSheet(f"background-color:white; border-left:5px solid {c}; border-radius:10px;")
        l = QVBoxLayout(f); l.addWidget(QLabel(t, styleSheet="color:#777; font-weight:bold")); l.addWidget(QLabel(v, styleSheet=f"color:{c}; font-size:20px; font-weight:bold")); return f

    # FIX: Refactored to return the Layout Object directly
    def createScrollBox(self, title):
        f = QFrame()
        l = QVBoxLayout(f)
        l.addWidget(QLabel(title, styleSheet="font-weight:bold; font-size:16px"))
        
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setFrameShape(QFrame.NoFrame)
        
        # --- FIX: FORCE VERTICAL SCROLL ONLY ---
        s.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        w = QWidget()
        v_layout = QVBoxLayout(w)
        v_layout.setAlignment(QtCore.Qt.AlignTop) # Keeps items at the top
        
        s.setWidget(w)
        l.addWidget(s)
        
        return f, v_layout # Return Frame AND Layout

    def createUploadPage(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(40,40,40,40); c = QFrame(); c.setFixedWidth(600); c.setStyleSheet("background-color: white; border-radius: 15px; border: 1px solid #dcdcdc;"); cl = QVBoxLayout(c); cl.setContentsMargins(30,30,30,30); cl.setSpacing(15)
        cl.addWidget(QLabel("Publish New Game", styleSheet="font-size: 22px; font-weight: bold; color: #2c3e50;"))
        self.input_title = QLineEdit(placeholderText="Game Title"); self.styleInp(self.input_title); cl.addWidget(self.input_title)
        gr = QHBoxLayout(); self.input_genre = QComboBox(); self.input_genre.addItems(["Action", "RPG", "Strategy", "Horror"]); self.styleInp(self.input_genre); self.input_new_genre = QLineEdit(placeholderText="New Genre"); self.styleInp(self.input_new_genre); self.btn_add_genre = QPushButton("+"); self.btn_add_genre.setFixedWidth(30); self.btn_add_genre.setStyleSheet("background-color: #2c3e50; color: white; border-radius: 5px;")
        gr.addWidget(self.input_genre); gr.addWidget(self.input_new_genre); gr.addWidget(self.btn_add_genre); cl.addLayout(gr)
        row_ps = QHBoxLayout(); self.input_price = QLineEdit(placeholderText="Price ($)"); self.styleInp(self.input_price); self.input_size = QLineEdit(placeholderText="Size (GB)"); self.styleInp(self.input_size); row_ps.addWidget(self.input_price); row_ps.addWidget(self.input_size); cl.addLayout(row_ps)
        self.input_desc = QTextEdit(placeholderText="Description..."); self.input_desc.setMaximumHeight(100); self.input_desc.setStyleSheet("border: 1px solid #ccc; border-radius: 5px;"); cl.addWidget(self.input_desc)
        pr = QHBoxLayout(); self.btn_browse_pic = QPushButton("Select Image"); self.lbl_pic_path = QLabel(""); pr.addWidget(self.btn_browse_pic); pr.addWidget(self.lbl_pic_path); cl.addLayout(pr)
        fr = QHBoxLayout(); self.btn_browse_file = QPushButton("Select File"); self.lbl_file_path = QLabel(""); fr.addWidget(self.btn_browse_file); fr.addWidget(self.lbl_file_path); cl.addLayout(fr)
        self.btn_publish = QPushButton("PUBLISH", styleSheet="background-color: #27ae60; color: white; font-weight: bold; padding: 10px; border-radius: 5px;"); cl.addWidget(self.btn_publish)
        l.addWidget(c, 0, QtCore.Qt.AlignCenter); self.stack.addWidget(p)

    def styleInp(self, w): w.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 5px; background-color: #f9f9f9;")
    
    # --- ANALYTICS & SALES ---
    def createAnalyticsPage(self):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(40,40,40,40)
        l.addWidget(QLabel("Analytics", styleSheet="font-size: 24px; font-weight: bold;"))
        l.addSpacing(20); l.addWidget(QLabel("GRAPH PLACEHOLDER", alignment=QtCore.Qt.AlignCenter, styleSheet="background-color: white; border: 2px dashed #bdc3c7; border-radius: 15px; color: #bdc3c7; font-size: 20px; font-weight: bold;")); l.addSpacing(20)
        
        # EXPORT BUTTON ADDED
        btn_row = QHBoxLayout()
        self.btn_view_sales = QPushButton("View Sales Report", styleSheet="background-color: #2980b9; color: white; padding: 15px; border-radius: 8px; font-weight: bold;")
        self.btn_export_excel = QPushButton("Export to Excel", styleSheet="background-color: #27ae60; color: white; padding: 15px; border-radius: 8px; font-weight: bold;")
        
        btn_row.addWidget(self.btn_view_sales)
        btn_row.addWidget(self.btn_export_excel)
        l.addLayout(btn_row)
        
        self.stack.addWidget(p)

    def createGameSalesPage(self, db):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(40,40,40,40)
        self.btn_back_analytics = QPushButton("← Back", styleSheet="border:none; color:#2980b9; text-align:left; font-weight:bold"); l.addWidget(self.btn_back_analytics)
        l.addWidget(QLabel("Sales Report", styleSheet="font-size:24px; font-weight:bold; margin-bottom:20px"))
        s = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); w = QWidget(); self.sales_layout = QVBoxLayout(w); self.sales_layout.setAlignment(QtCore.Qt.AlignTop); s.setWidget(w); l.addWidget(s)
        self.stack.addWidget(p)

    def createCommunityPage(self, n): 
        self.Community = QWidget(); l=QVBoxLayout(self.Community); l.setContentsMargins(0,0,0,0)
        h = QFrame(); h.setFixedHeight(100); h.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2980b9, stop:1 #6dd5fa); border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;"); hl=QVBoxLayout(h); hl.setContentsMargins(40,20,40,20)
        hl.addWidget(QLabel("COMMUNITY HUB", styleSheet="font-size:28px; font-weight:bold; color:white")); l.addWidget(h)
        c = QWidget(); cl = QVBoxLayout(c); cl.setContentsMargins(40,20,40,40); cl.setSpacing(20)
        i=QFrame(); i.setStyleSheet("background-color:white; border-radius:15px; border:1px solid #ddd;"); il=QVBoxLayout(i)
        self.addText_community=QTextEdit(placeholderText="Share your thoughts..."); self.addText_community.setMaximumHeight(80); self.addText_community.setStyleSheet("border:none;"); il.addWidget(self.addText_community)
        self.button_addComment=QPushButton("Post Update", cursor=QtCore.Qt.PointingHandCursor, styleSheet="background-color:#2980b9; color:white; padding:8px 20px; border-radius:20px; font-weight:bold"); il.addWidget(self.button_addComment, 0, QtCore.Qt.AlignRight); cl.addWidget(i)
        cl.addWidget(QLabel("Recent Activity", styleSheet="font-size:18px; font-weight:bold; margin-top:10px"))
        s=QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); 
        s.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        s.setStyleSheet("background-color:transparent"); w=QWidget(); w.setStyleSheet("background-color:transparent"); self.community_layout=QVBoxLayout(w); self.community_layout.setAlignment(QtCore.Qt.AlignTop); s.setWidget(w); cl.addWidget(s)
        l.addWidget(c); self.stack.addWidget(self.Community)

    def createCommentHistoryPage(self): 
        self.HistoryPage = QWidget(); l=QVBoxLayout(self.HistoryPage); l.setContentsMargins(40,40,40,40)
        self.btn_back_history = QPushButton("← Back", styleSheet="border:none; color:#2980b9; text-align:left; font-weight:bold"); l.addWidget(self.btn_back_history)
        l.addWidget(QLabel("History", styleSheet="font-size:22px; font-weight:bold")); 
        
        # --- FIX: FORCE VERTICAL SCROLL ---
        s=QScrollArea(widgetResizable=True); 
        s.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        w=QWidget(); self.history_layout=QVBoxLayout(w); self.history_layout.setAlignment(QtCore.Qt.AlignTop); s.setWidget(w); l.addWidget(s); self.stack.addWidget(self.HistoryPage)

    def createPublisherGameViewPage(self): 
        self.PubGameView = QWidget(); l = QVBoxLayout(self.PubGameView); top = QFrame(styleSheet="background-color: white; border-bottom: 1px solid #ddd;"); tb = QHBoxLayout(top); self.btn_back_viewPage = QPushButton("Back"); tb.addWidget(self.btn_back_viewPage); tb.addStretch(); l.addWidget(top)
        
        # --- FIX: FORCE VERTICAL SCROLL ---
        s = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); 
        s.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        w = QWidget(); cl = QVBoxLayout(w); cl.setContentsMargins(40,30,40,40); h = QHBoxLayout(); self.pv_image = QLabel("IMG", alignment=QtCore.Qt.AlignCenter, styleSheet="background-color: #2c3e50; color: white; border-radius: 12px; min-width: 300px; min-height: 400px;"); h.addWidget(self.pv_image)
        dc = QVBoxLayout(); self.pv_title = QLabel("Title", styleSheet="font-size: 42px; font-weight: 800;"); self.pv_publisher = QLabel("Pub"); self.pv_genre = QLabel("Genre"); self.pv_size = QLabel("Size"); self.pv_downloads = QLabel("DLs"); self.pv_price = QLabel("Price"); self.pv_btn_edit = QPushButton("Edit"); self.pv_btn_del = QPushButton("Delete")
        dc.addWidget(self.pv_title); dc.addWidget(self.pv_publisher); dc.addWidget(self.pv_genre); dc.addWidget(self.pv_size); dc.addWidget(self.pv_downloads); dc.addWidget(self.pv_price); dc.addWidget(self.pv_btn_edit); dc.addWidget(self.pv_btn_del); dc.addStretch(); h.addLayout(dc); cl.addLayout(h)
        
        # --- FIX: WORD WRAP FOR DESCRIPTION ---
        self.pv_desc = QLabel("Desc"); 
        self.pv_desc.setWordWrap(True)
        # CRITICAL FIX: Forces label to wrap instead of expanding window
        self.pv_desc.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        cl.addWidget(self.pv_desc)
        
        cl.addWidget(QLabel("REVIEWS (Admin/Pub Mode)", styleSheet="font-size:18px; font-weight:bold; border-bottom:2px solid #eee; margin-top:20px")); 
        self.pv_reviews_widget = QWidget(); self.pv_reviews_layout = QVBoxLayout(self.pv_reviews_widget); cl.addWidget(self.pv_reviews_widget); s.setWidget(w); l.addWidget(s); self.stack.addWidget(self.PubGameView)

    def createProfilePage(self, mw):
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(0,0,0,0); c = QFrame(); c.setFixedWidth(500); c.setStyleSheet("background-color: white; border-radius: 15px; border: 1px solid #e0e0e0;"); cl = QVBoxLayout(c); cl.setContentsMargins(0,0,0,30); cl.setSpacing(10)
        cl.addWidget(QFrame(styleSheet="background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e67e22, stop:1 #f1c40f); border-top-left-radius: 15px; border-top-right-radius: 15px; min-height: 120px;"))
        
        # --- SAFE PROFILE PIC INITIALIZATION (Fixes crash) ---
        initial = mw.fname[0].upper() if mw.fname else "?"
        self.lbl_pfp = QLabel(initial, alignment=QtCore.Qt.AlignCenter, styleSheet="background-color: #34495e; color: white; border-radius: 50px; font-size: 40px; border: 5px solid white; min-width: 100px; min-height: 100px;")
        
        cl.addWidget(self.lbl_pfp, 0, QtCore.Qt.AlignCenter)
        self.lbl_name_profile = QLabel(f"{mw.fname} {mw.lname}", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size: 22px; font-weight: bold; color: #2c3e50;"); cl.addWidget(self.lbl_name_profile)
        info = QWidget(); gl = QGridLayout(info); gl.setContentsMargins(40,0,40,0); gl.setSpacing(10)
        self.lbl_user_profile = QLabel(f"@{mw.publisher_name}"); self.lbl_email_profile = QLabel(mw.email)
        gl.addWidget(QLabel("Username:", styleSheet="color:#7f8c8d; font-weight:bold;"), 0, 0); gl.addWidget(self.lbl_user_profile, 0, 1)
        gl.addWidget(QLabel("Email:", styleSheet="color:#7f8c8d; font-weight:bold;"), 1, 0); gl.addWidget(self.lbl_email_profile, 1, 1)
        v_txt = "✓ VERIFIED" if mw.is_verified else "⚠ UNVERIFIED"; gl.addWidget(QLabel("Status:", styleSheet="color:#7f8c8d; font-weight:bold;"), 2, 0); gl.addWidget(QLabel(v_txt, styleSheet="color: #27ae60; font-weight: bold;"), 2, 1)
        cl.addWidget(info); cl.addSpacing(10)
        self.lbl_balance = QLabel(f"Balance: ${mw.withdrawable_balance:,.2f}", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size: 18px; font-weight: bold; color: #27ae60;"); cl.addWidget(self.lbl_balance)
        self.transfer_btn = QPushButton("Transfer Funds to Bank", cursor=QtGui.QCursor(QtCore.Qt.PointingHandCursor), styleSheet="background-color: #27ae60; color: white; font-weight: bold; padding: 10px; border-radius: 5px; margin: 0 40px;"); cl.addWidget(self.transfer_btn)
        row = QHBoxLayout(); self.btn_sold_profile = QPushButton("Total Games"); self.btn_comm_profile = QPushButton("Comments"); self.editProfile_btn = QPushButton("Edit Profile")
        for b in [self.btn_sold_profile, self.btn_comm_profile]: b.setStyleSheet("background-color: #f9f9f9; border: 1px solid #eee; padding: 10px; border-radius: 5px; font-weight: bold; color: #555;"); row.addWidget(b)
        self.editProfile_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 10px; border-radius: 5px; font-weight: bold;"); cl.addLayout(row); cl.addWidget(self.editProfile_btn)
        l.addWidget(c, 0, QtCore.Qt.AlignCenter); self.stack.addWidget(p)
    def styleInp(self, w): w.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 5px; background-color: #f9f9f9;")

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    
    # --- APPLY THEME ---
    if ThemeManager:
        theme_manager = ThemeManager()
        theme_manager.apply_theme(app)
    # -------------------

    window = PublisherWindow() 
    window.show()
    sys.exit(app.exec_())