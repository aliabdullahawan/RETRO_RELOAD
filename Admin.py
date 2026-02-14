import sys
import os  # REQUIRED FOR PATH FINDING
import datetime
import random
import re
import pyodbc
import csv
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QScrollArea, QLineEdit, QComboBox, QTextEdit, QGridLayout, QDialog, QSplitter

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
            print(f"DB Connection Error: {e}")
            return None

    # --- ADMIN FETCHERS ---
    def fetch_admin_dashboard_stats(self):
        conn = self.get_connection()
        if not conn: return None
        cursor = conn.cursor()
        try:
            cursor.execute("EXEC sp_GetAdminDashboard")
            row = cursor.fetchone()
            return row
        finally:
            conn.close()

    def fetch_online_users(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor()
        data = []
        try:
            # Returns: Username, Role (Limit handled in SQL Procedure TOP 20)
            cursor.execute("EXEC sp_GetOnlineUsers")
            for r in cursor.fetchall():
                data.append(r) 
        except Exception as e:
            print(f"DB Error Fetching Online Users: {e}")
        finally: 
            conn.close()
        return data

    def fetch_all_users(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor()
        data = []
        try:
            cursor.execute("EXEC sp_GetAllUsers")
            for r in cursor.fetchall():
                data.append({"id": r.User_ID, "name": r.User_username, "email": r.User_Email, "joined": str(r.Joining_date), "balance": float(r.Wallet_Balance), "online": r.is_online})
        finally: conn.close()
        return data

    def fetch_all_publishers(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor()
        data = []
        try:
            cursor.execute("EXEC sp_GetAllPublishers")
            for r in cursor.fetchall():
                data.append({"id": r.User_ID, "name": r.User_username, "email": r.User_Email, "joined": str(r.Joining_date), "revenue": float(r.Wallet_Balance), "online": r.is_online})
        finally: conn.close()
        return data

    def fetch_all_games(self):
        conn = self.get_connection()
        if not conn: return {}
        cursor = conn.cursor()
        games = {}
        try:
            cursor.execute("EXEC sp_GetStoreGames")
            for row in cursor.fetchall():
                # Attempt to fetch image safely
                img_data = getattr(row, 'Game_Icon', None)
                if not img_data: img_data = getattr(row, 'Game_Image', None)
                if not img_data: img_data = getattr(row, 'Image', None)

                games[row.Game_ID] = {
                    "title": row.Title, 
                    "price": float(row.Price), 
                    "publisher": row.Publisher,
                    "genre": row.Genre, 
                    "size": f"{row.Size} GB", 
                    "sold": row.Downloads,
                    "desc": getattr(row, 'Desc', 'No description'),
                    "image": img_data, 
                    "reviews": [] 
                }
        finally: conn.close()
        return games

    def fetch_all_transactions(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor()
        data = []
        try:
            cursor.execute("EXEC sp_GetAllTransactions")
            for r in cursor.fetchall():
                data.append({"date": str(r.Trans_date), "user": r.User_username, "item": r.Game_name, "amt": float(r.Trans_Amount)})
        finally: conn.close()
        return data

    def fetch_global_reviews(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor()
        data = []
        try:
            cursor.execute("EXEC sp_GetAllReviews")
            for r in cursor.fetchall():
                data.append(r)
        finally: conn.close()
        return data

    # --- REPORTING ---
    def fetch_report_user_activity(self):
        conn = self.get_connection(); cursor = conn.cursor(); data = []
        try: cursor.execute("EXEC sp_Report_UserActivity"); data = cursor.fetchall()
        finally: conn.close()
        return data

    def fetch_report_publisher_activity(self):
        conn = self.get_connection(); cursor = conn.cursor(); data = []
        try: cursor.execute("EXEC sp_Report_PublisherActivity"); data = cursor.fetchall()
        finally: conn.close()
        return data

    def fetch_report_transactions(self):
        conn = self.get_connection(); cursor = conn.cursor(); data = []
        try: cursor.execute("EXEC sp_Report_AllTransactions"); data = cursor.fetchall()
        finally: conn.close()
        return data

    # --- ACTIONS ---
    def delete_user(self, uid):
        conn = self.get_connection(); cursor = conn.cursor()
        try: cursor.execute("EXEC sp_DeleteUser ?", (uid,)); conn.commit(); return True
        except: return False
        finally: conn.close()

    def delete_game(self, gid):
        conn = self.get_connection(); cursor = conn.cursor()
        try: cursor.execute("EXEC sp_DeleteGame ?", (gid,)); conn.commit(); return True
        except: return False
        finally: conn.close()

    def delete_post(self, pid):
        conn = self.get_connection(); cursor = conn.cursor()
        try: cursor.execute("EXEC sp_DeletePost ?", (pid,)); conn.commit(); return True
        except: return False
        finally: conn.close()

    def delete_review(self, rid):
        conn = self.get_connection(); cursor = conn.cursor()
        try: cursor.execute("EXEC sp_DeleteReview ?", (rid,)); conn.commit(); return True
        except: return False
        finally: conn.close()

    # --- PROFILE ---
    def fetch_user_info(self, uid):
        conn = self.get_connection(); cursor = conn.cursor(); data = None
        try:
            cursor.execute("EXEC sp_GetUserInfo ?", (uid,))
            r = cursor.fetchone()
            if r:
                data = {
                    "fname": r.User_fname, "lname": r.User_Lname, 
                    "username": r.User_username, "email": r.User_Email, 
                    "balance": float(r.Wallet_Balance), "pfp": r.User_ProfilePic, 
                    "pass": getattr(r, 'User_Password', ''), "card": getattr(r, 'Card_Number', '')
                }
        finally: conn.close()
        return data

    def update_profile(self, uid, f, l, u, e, p, c):
        conn = self.get_connection(); cursor = conn.cursor()
        try: cursor.execute("EXEC sp_UpdateUserProfile ?, ?, ?, ?, ?, ?, ?", (uid, f, l, u, e, p, c)); conn.commit(); return True
        except: return False
        finally: conn.close()
    
    def update_profile_pic(self, uid, img):
        conn = self.get_connection(); cursor = conn.cursor()
        try: cursor.execute("EXEC sp_UpdateUserProfilePic ?, ?", (uid, img)); conn.commit(); return True
        except: return False
        finally: conn.close()

    def withdraw_funds(self, uid, amt):
        conn = self.get_connection(); cursor = conn.cursor()
        try:
            cursor.execute("EXEC sp_WithdrawFunds ?, ?", (uid, amt))
            row = cursor.fetchone()
            if row and row[0]==1: conn.commit(); return True
            return False
        except: return False
        finally: conn.close()

    def fetch_community_feed(self):
        conn = self.get_connection(); cursor = conn.cursor(); posts = []
        try:
            cursor.execute("EXEC sp_GetCommunityFeed")
            for r in cursor.fetchall():
                posts.append({"id": r.Com_ID, "user": r.Username, "role": r.User_Role, "text": r.Comment, "date": str(r.Comment_Date)})
        finally: conn.close()
        return posts
        
    def fetch_my_comments(self, uid):
        conn = self.get_connection(); cursor = conn.cursor(); posts = []
        try:
            cursor.execute("EXEC sp_GetUserComments ?", (uid,))
            for row in cursor.fetchall():
                posts.append({"id": row.Com_ID, "text": row.Comment, "date": str(row.Comment_Date)})
        finally: conn.close()
        return posts

    def add_post(self, uid, txt):
        conn = self.get_connection(); cursor = conn.cursor()
        try: cursor.execute("EXEC sp_AddCommunityPost ?, ?", (uid, txt)); conn.commit()
        finally: conn.close()
    
    def fetch_game_reviews(self, gid):
        conn = self.get_connection(); cursor = conn.cursor(); reviews = []
        try:
            cursor.execute("EXEC sp_GetReviewsByGame ?", (gid,))
            for r in cursor.fetchall(): reviews.append((r.Reviewer, r.Review_Text, r.Rating, r.Review_ID))
        finally: conn.close()
        return reviews

# --- Main Window Class ---
class AdminWindow(QtWidgets.QMainWindow):
    def __init__(self, admin_data=None, db_config=None):
        super().__init__()
        self.ui = Ui_AdminWindow()
        
        self.admin_name = "SuperAdmin"
        self.email = "admin@retroreload.com"
        self.fname = "System"; self.lname = "Root"
        self.user_db_id = 1
        self.user_full_info = {}

        if admin_data:
            if hasattr(admin_data, 'username'): self.admin_name = admin_data.username
            if hasattr(admin_data, 'email'): self.email = admin_data.email
            if hasattr(admin_data, 'id'): self.user_db_id = admin_data.id

        self.db = DatabaseManager(db_config)
        self.profile_pic_data = None
        self.admin_balance = 0.0
        self.games_db = {}
        self.community_posts = []

        self.ui.setupUi(self)
        self.setWindowTitle("Retro Reload - Admin Control Panel")
        
        # --- FIX: USE RESOURCE PATH FOR ICON ---
        self.setWindowIcon(QtGui.QIcon(resource_path('Icon.png')))
        
        self.setup_connections()
        self.refresh_all_data()

    def setup_connections(self):
        self.ui.btn_dashboard.clicked.connect(lambda: self.ui.stack.setCurrentIndex(0))
        self.ui.btn_users.clicked.connect(lambda: self.ui.stack.setCurrentIndex(1))
        self.ui.btn_publishers.clicked.connect(lambda: self.ui.stack.setCurrentIndex(2))
        self.ui.btn_games.clicked.connect(lambda: self.ui.stack.setCurrentIndex(3))
        self.ui.btn_transactions.clicked.connect(lambda: self.ui.stack.setCurrentIndex(4))
        self.ui.btn_community.clicked.connect(lambda: self.ui.stack.setCurrentIndex(5))
        self.ui.btn_profile.clicked.connect(lambda: self.ui.stack.setCurrentIndex(6))
        self.ui.btn_logout.clicked.connect(self.logoutFunc)
        
        self.ui.btn_card_games.clicked.connect(lambda: self.ui.stack.setCurrentIndex(3))
        self.ui.btn_card_community.clicked.connect(lambda: self.ui.stack.setCurrentIndex(5))
        self.ui.btn_card_reviews.clicked.connect(self.openGlobalReviews)
        
        self.ui.btn_edit_profile.clicked.connect(self.openEditProfileDialog)
        self.ui.btn_change_pic.clicked.connect(self.changeProfilePicture)
        self.ui.btn_transfer.clicked.connect(self.transferMoneyFunc)
        
        self.ui.btn_back_gameDetails.clicked.connect(lambda: self.ui.stack.setCurrentIndex(3))
        self.ui.btn_back_reviews.clicked.connect(lambda: self.ui.stack.setCurrentIndex(0))
        self.ui.button_addComment.clicked.connect(self.postAdminComment)
        self.ui.btn_export_excel.clicked.connect(self.exportTransactionsToExcel)
        self.ui.btn_comm_profile.clicked.connect(lambda: self.ui.stack.setCurrentIndex(9))
        self.ui.btn_back_history.clicked.connect(lambda: self.ui.stack.setCurrentIndex(6))

    # --- ROBUST REFRESH FUNCTION ---
    def refresh_all_data(self):
        print("--- REFRESHING ADMIN DATA ---") 
        
        # 1. Dashboard Stats
        try:
            stats = self.db.fetch_admin_dashboard_stats()
            if stats:
                 # Users, Pubs, Games, Revenue, Posts, Reviews
                 self.ui.updateDashboardStats(stats[2], stats[4], stats[5])
                 self.admin_balance = float(stats[3]) if stats[3] else 0.0
        except Exception as e:
            print(f"Stats Error: {e}")

        # 2. Online Users (Separated to ensure UI updates even if DB fails)
        self.ui.clearLayout(self.ui.online_layout)
        
        # ALWAYS ADD ADMIN FIRST
        self.ui.addOnlineRow(self.admin_name, "Administrator", True)
        
        try:
            online_users = self.db.fetch_online_users()
            print(f"Online Users Found: {len(online_users)}") 
            for u in online_users:
                # u[0] is Username, u[1] is Role
                if u[0] != self.admin_name:
                    self.ui.addOnlineRow(u[0], u[1], True)
        except Exception as e:
            print(f"Online Users Error: {e}")
        
        self.ui.online_layout.addStretch()

        # 3. User Lists
        try:
            users = self.db.fetch_all_users()
            self.ui.populateUsers(users, self)
        except Exception as e: print(f"Users List Error: {e}")

        # 4. Publisher Lists
        try:
            publishers = self.db.fetch_all_publishers()
            self.ui.populatePublishers(publishers, self)
        except Exception as e: print(f"Pub List Error: {e}")

        # 5. Games & Transactions
        try:
            self.games_db = self.db.fetch_all_games()
            self.ui.populateGames(self.games_db, self)

            trans = self.db.fetch_all_transactions()
            self.ui.populateTransactions(trans)

            recent_reviews = self.db.fetch_global_reviews()
            self.ui.updateDashboardLists(trans, recent_reviews)
        except Exception as e: print(f"Games/Trans Error: {e}")

        # 6. Community
        try:
            self.community_posts = self.db.fetch_community_feed()
            self.ui.populateCommunity(self.community_posts, self)
        except Exception as e: print(f"Community Error: {e}")
            
        # 7. Profile Info
        try:
            info = self.db.fetch_user_info(self.user_db_id)
            if info:
                self.user_full_info = info
                self.fname = info['fname']; self.lname = info['lname']
                self.admin_name = info['username']; self.email = info['email']
                self.profile_pic_data = info['pfp']
                self.admin_balance = info['balance']
                
                self.ui.updateProfileLabels(self.fname, self.lname, self.admin_name, self.email)
                self.ui.lbl_balance.setText(f"Wallet Balance: ${self.admin_balance:,.2f}")
                
                if self.profile_pic_data:
                    pixmap = QtGui.QPixmap(); pixmap.loadFromData(self.profile_pic_data)
                    self.ui.lbl_pfp.setPixmap(pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation))
                    self.ui.lbl_pfp.setText("")
                else:
                    self.ui.lbl_pfp.setText(self.fname[0].upper())
        except Exception as e: print(f"Profile Error: {e}")
            
        # 8. History
        try:
            my_comments = self.db.fetch_my_comments(self.user_db_id)
            self.ui.btn_comm_profile.setText(f"{len(my_comments)}\nComments")
            self.ui.populateHistory(my_comments, self)
        except Exception as e: print(f"History Error: {e}")

    # --- ACTIONS ---
    def exportTransactionsToExcel(self):
        try:
            fname, _ = QFileDialog.getSaveFileName(self, "Export Report", "", "CSV Files (*.csv)")
            if fname:
                user_act = self.db.fetch_report_user_activity()
                pub_act = self.db.fetch_report_publisher_activity()
                trans_log = self.db.fetch_report_transactions()
                with open(fname, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(["RETRO RELOAD - EXECUTIVE REPORT"])
                    writer.writerow([f"Date: {datetime.datetime.now()}"])
                    writer.writerow([])
                    writer.writerow(["--- PUBLISHER PERFORMANCE ---"])
                    writer.writerow(["Publisher", "Games", "Revenue", "Earnings (80%)"])
                    for r in pub_act: writer.writerow([r[0], r[1], f"${float(r[2]):.2f}", f"${float(r[2])*0.8:.2f}"])
                    writer.writerow([])
                    writer.writerow(["--- USER SPENDING ---"])
                    writer.writerow(["User", "Role", "Games", "Spent"])
                    for r in user_act: writer.writerow([r[0], r[1], r[2], f"${float(r[3]):.2f}"])
                    writer.writerow([])
                    writer.writerow(["--- TRANSACTIONS ---"])
                    for r in trans_log: writer.writerow([str(r[0]), r[1], r[2], f"${r[3]:.2f}"])
                QMessageBox.information(self, "Success", "Report exported.")
        except Exception as e: QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def deleteUserFunc(self, uid, name):
        if QMessageBox.question(self, "Delete", f"Delete {name}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_user(uid): self.refresh_all_data(); QMessageBox.information(self, "Deleted", "User removed.")

    def deletePublisherFunc(self, pid, name):
        if QMessageBox.question(self, "Delete", f"Delete {name}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_user(pid): self.refresh_all_data(); QMessageBox.information(self, "Deleted", "Publisher removed.")

    def openGameDetails(self, gid):
        g = self.games_db.get(gid)
        if not g: return
        self.current_view_game_id = gid
        
        self.ui.gd_title.setText(g['title'])
        self.ui.gd_publisher.setText(f"Publisher: {g['publisher']}")
        self.ui.gd_genre.setText(f"Genre: {g['genre']}")
        self.ui.gd_size.setText(f"Size: {g['size']}")
        self.ui.gd_price.setText(f"Price: ${g['price']}")
        self.ui.gd_sold.setText(f"Sold: {g['sold']}")
        revenue = g['price'] * g['sold']
        self.ui.gd_revenue.setText(f"Revenue: ${revenue:,.2f}")
        self.ui.gd_desc.setText(g['desc'])
        
        if g.get('image'):
            try:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(g['image'])
                self.ui.gd_image.setPixmap(pixmap.scaled(200, 300, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                self.ui.gd_image.setText("")
            except:
                self.ui.gd_image.setText(g['title'])
                self.ui.gd_image.setPixmap(QtGui.QPixmap())
        else:
            self.ui.gd_image.setText(g['title'])
            self.ui.gd_image.setPixmap(QtGui.QPixmap())
        
        self.refreshGameReviews(gid)
        try: self.ui.btn_delete_game.clicked.disconnect()
        except: pass
        self.ui.btn_delete_game.clicked.connect(lambda: self.deleteGameFunc(gid))
        self.ui.stack.setCurrentIndex(7)

    def refreshGameReviews(self, gid):
        self.ui.clearLayout(self.ui.reviews_layout)
        reviews = self.db.fetch_game_reviews(gid)
        if not reviews: self.ui.reviews_layout.addWidget(QLabel("No reviews."))
        else:
            for u, t, r, rid in reviews:
                self.ui.reviews_layout.addWidget(self.ui.createAdminReviewCard(u, t, r, rid, gid, self))

    def deleteGameFunc(self, gid):
        if QMessageBox.question(self, "Delete", "Delete Game?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_game(gid):
                self.refresh_all_data(); self.ui.stack.setCurrentIndex(3); QMessageBox.information(self, "Deleted", "Game deleted.")

    def deleteReviewFunc(self, rid, gid):
        if QMessageBox.question(self, "Delete", "Delete Review?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_review(rid):
                if self.ui.stack.currentIndex() == 8: self.openGlobalReviews()
                else: self.refreshGameReviews(gid)
                QMessageBox.information(self, "Deleted", "Review deleted.")

    def deletePostFunc(self, pid):
        if QMessageBox.question(self, "Delete", "Delete Post?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_post(pid): self.refresh_all_data(); QMessageBox.information(self, "Deleted", "Post deleted.")

    def postAdminComment(self):
        t = self.ui.addText_community.toPlainText().strip()
        if t:
            self.db.add_post(self.user_db_id, t)
            self.refresh_all_data(); self.ui.addText_community.clear()

    def openGlobalReviews(self):
        self.ui.clearLayout(self.ui.global_reviews_layout)
        reviews = self.db.fetch_global_reviews()
        if not reviews: self.ui.global_reviews_layout.addWidget(QLabel("No reviews found."))
        else:
            for r in reviews:
                card = self.ui.createGlobalReviewCard(r[1], r[2], r[4], r[3], r[6], r[0], self)
                self.ui.global_reviews_layout.addWidget(card)
        self.ui.stack.setCurrentIndex(8)

    def changeProfilePicture(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select Pic', 'c:\\', "Images (*.jpg *.png)")
        if fname:
            with open(fname, 'rb') as f: binary = f.read()
            if self.db.update_profile_pic(self.user_db_id, binary):
                self.refresh_all_data(); QMessageBox.information(self, "Success", "Picture Updated")

    def openEditProfileDialog(self):
        d = QDialog(self); d.setWindowTitle("Edit"); d.setFixedSize(300, 500); l = QVBoxLayout(d)
        def add_f(lbl, val):
            l.addWidget(QLabel(lbl)); le = QLineEdit(str(val) if val else ""); l.addWidget(le); return le
        ef = add_f("First Name", self.user_full_info.get('fname'))
        el = add_f("Last Name", self.user_full_info.get('lname'))
        eu = add_f("Username", self.user_full_info.get('username'))
        ee = add_f("Email", self.user_full_info.get('email'))
        ep = add_f("Password", self.user_full_info.get('pass')); ep.setEchoMode(QLineEdit.Password)
        ec = add_f("Card", self.user_full_info.get('card'))
        btn = QPushButton("Save"); l.addWidget(btn)
        btn.clicked.connect(lambda: self.saveProfile(d, ef.text(), el.text(), eu.text(), ee.text(), ep.text(), ec.text()))
        d.exec_()
        
    def saveProfile(self, d, f, l, u, e, p, c):
        if self.db.update_profile(self.user_db_id, f, l, u, e, p, c):
            self.refresh_all_data(); d.accept(); QMessageBox.information(self, "Success", "Updated")

    def transferMoneyFunc(self):
        if QMessageBox.question(self, "Transfer", f"Transfer ${self.admin_balance:,.2f}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.withdraw_funds(self.user_db_id, self.admin_balance):
                self.refresh_all_data(); QMessageBox.information(self, "Success", "Funds Transferred.")

    def logoutFunc(self):
        if QMessageBox.question(self, "Logout", "Are you sure?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes: QtWidgets.QApplication.quit()
    def closeEvent(self, e): self.logoutFunc(); e.ignore()

class Ui_AdminWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow"); MainWindow.resize(1200, 750); MainWindow.setStyleSheet("QMainWindow { background-color: #f0f2f5; }")
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.createSidebar(self.centralwidget); self.createStack(self.centralwidget)
        self.createDashboardPage(); self.createManageUsersPage(); self.createManagePubsPage()
        self.createManageGamesPage(); self.createTransactionsPage(); self.createCommunityPage()
        self.createProfilePage(MainWindow); self.createGameDetailsPage(); self.createGlobalReviewsPage(); self.createHistoryPage()
        MainWindow.setCentralWidget(self.centralwidget); self.stack.setCurrentIndex(0)

    def createSidebar(self, parent):
        self.frame = QFrame(parent); self.frame.setGeometry(0, 0, 180, 750); self.frame.setStyleSheet("background-color: white; border-right: 1px solid #dcdcdc;")
        l = QVBoxLayout(self.frame); l.setSpacing(10); l.setContentsMargins(10, 20, 10, 20)
        l.addWidget(QLabel("RETRO\nADMIN", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 20px;"))
        self.btn_dashboard = self.navBtn("DASHBOARD"); self.btn_users = self.navBtn("USERS"); self.btn_publishers = self.navBtn("PUBLISHERS")
        self.btn_games = self.navBtn("ALL GAMES"); self.btn_transactions = self.navBtn("TRANSACTIONS"); self.btn_community = self.navBtn("COMMUNITY"); self.btn_profile = self.navBtn("PROFILE")
        for b in [self.btn_dashboard, self.btn_users, self.btn_publishers, self.btn_games, self.btn_transactions, self.btn_community, self.btn_profile]: l.addWidget(b)
        l.addStretch(); self.btn_logout = self.navBtn("LOGOUT"); l.addWidget(self.btn_logout)

    def navBtn(self, text):
        btn = QPushButton(text); btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn.setStyleSheet("QPushButton { border: none; text-align: left; padding: 12px; color: #555; font-weight: bold; } QPushButton:hover { background-color: #f0f2f5; color: #2c3e50; border-radius: 5px; }")
        return btn

    def createStack(self, parent): self.stack = QtWidgets.QStackedWidget(parent); self.stack.setGeometry(181, 0, 1019, 750)

    def createDashboardPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.setContentsMargins(40,40,40,40); l.setSpacing(25)
        l.addWidget(QLabel("Admin Dashboard", styleSheet="font-size: 28px; font-weight: bold; color: #2c3e50;"))
        row = QHBoxLayout(); row.setSpacing(20)
        self.btn_card_games = self.btnStatCard("Total Games", "0", "#3498db")
        self.btn_card_community = self.btnStatCard("Total Posts", "0", "#e67e22")
        self.btn_card_reviews = self.btnStatCard("Total Reviews", "0", "#9b59b6")
        row.addWidget(self.btn_card_games); row.addWidget(self.btn_card_community); row.addWidget(self.btn_card_reviews)
        l.addLayout(row)
        split = QHBoxLayout(); split.setSpacing(20)
        self.dash_list_trans = self.scrollBox("Recent Transactions")
        self.dash_list_reviews = self.scrollBox("Recent Reviews")
        split.addWidget(self.dash_list_trans); split.addWidget(self.dash_list_reviews)
        l.addLayout(split)
        
        # --- FIXED ONLINE USERS SECTION ---
        l.addWidget(QLabel("Currently Online (Top 20)", styleSheet="font-size: 18px; font-weight: bold; margin-top: 10px;"))
        self.online_scroll = QScrollArea()
        self.online_scroll.setWidgetResizable(True) 
        self.online_scroll.setFrameShape(QFrame.NoFrame)
        self.online_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.online_content = QtWidgets.QWidget()
        self.online_layout = QVBoxLayout(self.online_content)
        self.online_layout.setAlignment(QtCore.Qt.AlignTop) 
        self.online_layout.setSpacing(5) 
        self.online_scroll.setWidget(self.online_content)
        self.online_scroll.setFixedHeight(200) 
        self.online_scroll.setStyleSheet("""
            QScrollArea { background-color: white; border-radius: 10px; border: 1px solid #ddd; }
            QScrollBar:vertical { width: 10px; background: #f1f1f1; }
            QScrollBar::handle:vertical { background: #888; border-radius: 5px; }
        """)
        l.addWidget(self.online_scroll)
        self.stack.addWidget(p)
    
    def btnStatCard(self, title, val, col):
        b = QPushButton(); b.setFixedSize(220, 100); b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        b.setStyleSheet(f"QPushButton {{ background-color: white; border-radius: 15px; border: 1px solid #e0e0e0; border-top: 5px solid {col}; text-align: center; }} QPushButton:hover {{ background-color: #f8f9fa; }}")
        l = QVBoxLayout(b); l.setSpacing(5); l.setContentsMargins(10,10,10,10)
        l.addWidget(QLabel(title, alignment=QtCore.Qt.AlignCenter, styleSheet="color: #7f8c8d; font-weight: bold; font-size: 14px; border: none;"))
        l.addWidget(QLabel(val, alignment=QtCore.Qt.AlignCenter, styleSheet=f"color: {col}; font-size: 28px; font-weight: bold; border: none;"))
        return b

    def scrollBox(self, title):
        f = QFrame(); f.setStyleSheet("background-color:white; border-radius:10px;"); l = QVBoxLayout(f)
        l.addWidget(QLabel(title, styleSheet="font-weight:bold; font-size:16px; color:#333; margin-bottom:5px"))
        s = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); w = QtWidgets.QWidget(); QVBoxLayout(w); s.setWidget(w); l.addWidget(s)
        return f 

    def updateDashboardStats(self, g, p, r):
        self.btn_card_games.layout().itemAt(1).widget().setText(str(g))
        self.btn_card_community.layout().itemAt(1).widget().setText(str(p))
        self.btn_card_reviews.layout().itemAt(1).widget().setText(str(r))

    def updateDashboardLists(self, trans, reviews):
        layout_t = self.dash_list_trans.findChild(QScrollArea).widget().layout(); self.clearLayout(layout_t)
        for t in trans[:10]: layout_t.addWidget(QLabel(f"{t['user']} bought {t['item']} (${t['amt']:.2f})", styleSheet="border-bottom:1px solid #eee; padding:5px; color:#555"))
        layout_r = self.dash_list_reviews.findChild(QScrollArea).widget().layout(); self.clearLayout(layout_r)
        for r in reviews[:10]: layout_r.addWidget(QLabel(f"{r[1]} on {r[2]}: {r[3]}★", styleSheet="border-bottom:1px solid #eee; padding:5px; color:#555"))

    def addOnlineRow(self, name, role, is_online):
        f = QFrame()
        f.setMinimumHeight(50) 
        f.setStyleSheet("QFrame { background-color: #f8f9fa; border-bottom: 1px solid #ddd; }")
        r = QHBoxLayout()
        f.setLayout(r) 
        r.setContentsMargins(10, 5, 10, 5)
        lbl_dot = QLabel("●")
        lbl_dot.setFixedWidth(20)
        lbl_dot.setStyleSheet("color: #27ae60; font-size: 16px; border: none;")
        r.addWidget(lbl_dot)
        display_name = str(name) if name else "Unknown"
        lbl_name = QLabel(display_name)
        lbl_name.setStyleSheet("color: #2c3e50; font-weight: bold; font-size: 14px; border: none;")
        r.addWidget(lbl_name)
        r.addStretch()
        display_role = str(role) if role else "User"
        lbl_role = QLabel(display_role)
        lbl_role.setStyleSheet("color: #7f8c8d; font-style: italic; border: none;")
        r.addWidget(lbl_role)
        self.online_layout.addWidget(f)

    def createManageUsersPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.addWidget(QLabel("Manage Users", styleSheet="font-size: 24px; font-weight: bold;"))
        self.users_scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); self.users_content = QtWidgets.QWidget(); self.users_layout = QVBoxLayout(self.users_content)
        self.users_scroll.setWidget(self.users_content); l.addWidget(self.users_scroll); self.stack.addWidget(p)

    def populateUsers(self, users, mw):
        self.clearLayout(self.users_layout)
        for u in users:
            f = QFrame(styleSheet="background-color: white; border-radius: 10px; border: 1px solid #eee; margin-bottom: 5px;"); r = QHBoxLayout(f)
            col = "#27ae60" if u['online'] else "#95a5a6"
            r.addWidget(QLabel("●", styleSheet=f"color: {col}; font-size: 20px;"))
            info = QVBoxLayout(); info.addWidget(QLabel(u['name'], styleSheet="font-weight: bold;")); info.addWidget(QLabel(f"Joined: {u['joined']}", styleSheet="color: #7f8c8d; font-size: 11px;")); r.addLayout(info); r.addStretch()
            stats = QVBoxLayout(); stats.addWidget(QLabel(f"Bal: ${u['balance']:.2f}", styleSheet="color:green; font-size:11px")); r.addLayout(stats); r.addSpacing(10)
            btn = QPushButton("Delete"); btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 5px;"); btn.clicked.connect(lambda ch, uid=u['id'], nm=u['name']: mw.deleteUserFunc(uid, nm)); r.addWidget(btn)
            self.users_layout.addWidget(f)
        self.users_layout.addStretch()

    def createManagePubsPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.addWidget(QLabel("Manage Publishers", styleSheet="font-size: 24px; font-weight: bold;"))
        self.pubs_scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); self.pubs_content = QtWidgets.QWidget(); self.pubs_layout = QVBoxLayout(self.pubs_content)
        self.pubs_scroll.setWidget(self.pubs_content); l.addWidget(self.pubs_scroll); self.stack.addWidget(p)

    def populatePublishers(self, pubs, mw):
        self.clearLayout(self.pubs_layout)
        for p in pubs:
            f = QFrame(styleSheet="background-color: white; border-radius: 10px; border: 1px solid #eee; margin-bottom: 5px;"); r = QHBoxLayout(f)
            col = "#27ae60" if p['online'] else "#95a5a6"
            r.addWidget(QLabel("●", styleSheet=f"color: {col}; font-size: 20px;"))
            info = QVBoxLayout(); info.addWidget(QLabel(p['name'], styleSheet="font-weight: bold;")); info.addWidget(QLabel(f"Joined: {p['joined']}", styleSheet="color: #7f8c8d; font-size: 11px;")); r.addLayout(info); r.addStretch()
            stats = QVBoxLayout(); stats.addWidget(QLabel(f"Rev: ${p['revenue']:.2f}", styleSheet="color: #27ae60; font-size:11px")); r.addLayout(stats); r.addSpacing(10)
            btn = QPushButton("Delete"); btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 5px;"); btn.clicked.connect(lambda ch, pid=p['id'], nm=p['name']: mw.deletePublisherFunc(pid, nm)); r.addWidget(btn)
            self.pubs_layout.addWidget(f)
        self.pubs_layout.addStretch()

    def createManageGamesPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.addWidget(QLabel("All Games", styleSheet="font-size: 24px; font-weight: bold;"))
        self.games_scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); self.games_content = QtWidgets.QWidget(); self.games_grid = QGridLayout(self.games_content); self.games_grid.setSpacing(20)
        self.games_scroll.setWidget(self.games_content); l.addWidget(self.games_scroll); self.stack.addWidget(p)

    def populateGames(self, games, mw):
        self.clearLayout(self.games_grid); idx = 0
        for gid, g in games.items():
            f = QFrame(); f.setFixedSize(160, 240); f.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd;")
            vl = QVBoxLayout(f); vl.setContentsMargins(10,10,10,10); vl.setSpacing(5)
            img_lbl = QLabel(alignment=QtCore.Qt.AlignCenter)
            img_lbl.setStyleSheet("background-color: #bdc3c7; border-radius: 5px; min-height: 80px;")
            if g.get('image'):
                try:
                    pix = QtGui.QPixmap(); pix.loadFromData(g['image'])
                    img_lbl.setPixmap(pix.scaled(140, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                except: img_lbl.setText(f"IMG {gid}")
            else: img_lbl.setText(f"IMG {gid}")
            vl.addWidget(img_lbl)
            vl.addWidget(QLabel(g['title'], styleSheet="font-weight: bold; font-size: 12px;"))
            vl.addWidget(QLabel(f"{g['publisher']}\n${g['price']} | Sold: {g['sold']}", styleSheet="color: #555; font-size: 10px;"))
            btn = QPushButton("Manage"); btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor)); btn.setStyleSheet("background-color: #2c3e50; color: white; border-radius: 4px; padding: 4px; font-size: 11px;")
            btn.clicked.connect(lambda ch, i=gid: mw.openGameDetails(i)); vl.addWidget(btn)
            self.games_grid.addWidget(f, idx//5, idx%5); idx+=1

    def createTransactionsPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.addWidget(QLabel("Transaction Logs", styleSheet="font-size: 24px; font-weight: bold;"))
        self.btn_export_excel = QPushButton("Generate Full Report (Excel)", styleSheet="background-color:#27ae60; color:white; padding:10px; font-weight:bold; border-radius:5px; margin-bottom:10px")
        l.addWidget(self.btn_export_excel)
        self.trans_scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); self.trans_content = QtWidgets.QWidget(); self.trans_layout = QVBoxLayout(self.trans_content)
        self.trans_scroll.setWidget(self.trans_content); l.addWidget(self.trans_scroll); self.stack.addWidget(p)

    def populateTransactions(self, trans):
        self.clearLayout(self.trans_layout)
        h = QHBoxLayout(); h.addWidget(QLabel("Date", styleSheet="font-weight:bold")); h.addWidget(QLabel("User", styleSheet="font-weight:bold")); h.addWidget(QLabel("Item", styleSheet="font-weight:bold")); h.addWidget(QLabel("Amount", styleSheet="font-weight:bold")); self.trans_layout.addLayout(h)
        for t in trans:
            r = QHBoxLayout(); r.addWidget(QLabel(t['date'])); r.addWidget(QLabel(t['user'])); r.addWidget(QLabel(t['item'])); r.addWidget(QLabel(f"${t['amt']:.2f}", styleSheet="color: #27ae60; font-weight:bold;"))
            f = QFrame(styleSheet="background-color: white; border-bottom: 1px solid #eee; padding: 5px;"); f.setLayout(r); self.trans_layout.addWidget(f)
        self.trans_layout.addStretch()

    def createCommunityPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.setContentsMargins(0,0,0,0)
        h = QFrame(); h.setFixedHeight(100); h.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2c3e50, stop:1 #34495e); border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;"); hl=QVBoxLayout(h); hl.setContentsMargins(40,20,40,20)
        hl.addWidget(QLabel("COMMUNITY MODERATION", styleSheet="font-size:28px; font-weight:bold; color:white")); l.addWidget(h)
        c = QWidget(); cl = QVBoxLayout(c); cl.setContentsMargins(40,20,40,40)
        inp = QFrame(styleSheet="background-color: white; border-radius: 15px; border:1px solid #ddd"); il = QVBoxLayout(inp)
        self.addText_community = QtWidgets.QTextEdit(placeholderText="Write admin announcement...", maximumHeight=80); self.addText_community.setStyleSheet("border:none"); il.addWidget(self.addText_community)
        self.button_addComment = QPushButton("Post as Admin", styleSheet="background-color: #c0392b; color: white; padding: 8px 20px; border-radius: 20px; font-weight: bold;"); il.addWidget(self.button_addComment, 0, QtCore.Qt.AlignRight); cl.addWidget(inp)
        cl.addWidget(QLabel("Feed:", styleSheet="font-weight: bold; margin-top: 10px;"))
        self.comm_scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.NoFrame); self.comm_content = QtWidgets.QWidget(); self.comm_layout = QVBoxLayout(self.comm_content)
        self.comm_scroll.setWidget(self.comm_content); cl.addWidget(self.comm_scroll); 
        l.addWidget(c); self.stack.addWidget(p)

    def populateCommunity(self, posts, mw):
        self.clearLayout(self.comm_layout)
        for post in posts:
            c = QFrame(styleSheet="background-color: white; border-radius: 10px; margin-bottom: 10px; border:1px solid #eee"); cl = QHBoxLayout(c)
            bg = "#e67e22" if post['role']=='Publisher' else ("#c0392b" if post['role']=='Admin' else "#3498db")
            cl.addWidget(QLabel(post['user'][0], alignment=QtCore.Qt.AlignCenter, styleSheet=f"background-color: {bg}; color: white; border-radius: 20px; font-weight: bold; min-width: 40px; min-height: 40px;"))
            vl = QVBoxLayout(); vl.addWidget(QLabel(f"<b>{post['user']}</b> <span style='color:#999; font-size:10px;'>{post['date']}</span>")); vl.addWidget(QLabel(post['text'], styleSheet="color: #555; word-wrap: break-word;")); cl.addLayout(vl); cl.addStretch()
            btn = QPushButton("Delete", styleSheet="background-color: #c0392b; color: white; border-radius: 5px; font-weight: bold; padding: 5px 10px;"); btn.clicked.connect(lambda ch, i=post['id']: mw.deletePostFunc(i)); cl.addWidget(btn)
            self.comm_layout.addWidget(c)
        self.comm_layout.addStretch()

    def createProfilePage(self, mw):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.setContentsMargins(0,0,0,0)
        c = QFrame(); c.setFixedWidth(500); c.setStyleSheet("background-color: white; border-radius: 15px; border: 1px solid #e0e0e0;"); cl = QVBoxLayout(c); cl.setContentsMargins(0,0,0,30)
        cl.addWidget(QFrame(styleSheet="background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2c3e50, stop:1 #34495e); border-top-left-radius: 15px; border-top-right-radius: 15px; min-height: 120px;"))
        self.lbl_pfp = QLabel(mw.fname[0].upper(), alignment=QtCore.Qt.AlignCenter, styleSheet="background-color: #2c3e50; color: white; border-radius: 50px; font-size: 40px; border: 5px solid white; min-width: 100px; min-height: 100px;"); cl.addWidget(self.lbl_pfp, 0, QtCore.Qt.AlignCenter)
        self.lbl_name_profile = QLabel(f"{mw.fname} {mw.lname}", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size: 22px; font-weight: bold; color: #2c3e50;"); cl.addWidget(self.lbl_name_profile)
        
        ig = QtWidgets.QWidget(); gl = QGridLayout(ig); gl.setContentsMargins(40,10,40,10)
        self.lbl_user_profile = QLabel(f"@{mw.admin_name}"); self.lbl_email_profile = QLabel(mw.email)
        gl.addWidget(QLabel("Username:", styleSheet="color:#777; font-weight:bold"), 0, 0); gl.addWidget(self.lbl_user_profile, 0, 1)
        gl.addWidget(QLabel("Email:", styleSheet="color:#777; font-weight:bold"), 1, 0); gl.addWidget(self.lbl_email_profile, 1, 1); cl.addWidget(ig)
        
        self.btn_change_pic = QPushButton("Change Picture", styleSheet="color: #2980b9; border: none; font-weight: bold;"); cl.addWidget(self.btn_change_pic)
        cl.addSpacing(10)
        self.lbl_balance = QLabel(f"System Revenue: ${mw.admin_balance:,.2f}", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size: 16px; font-weight: bold; color: #27ae60;"); cl.addWidget(self.lbl_balance)
        self.btn_transfer = QPushButton("Transfer to Bank", styleSheet="background-color: #27ae60; color: white; font-weight: bold; padding: 10px; border-radius: 5px; margin: 0 40px;"); cl.addWidget(self.btn_transfer); cl.addSpacing(20)
        self.btn_edit_profile = QPushButton("Edit Profile", styleSheet="background-color: #2c3e50; color: white; padding: 10px; border-radius: 5px; font-weight: bold; margin: 0 40px;"); cl.addWidget(self.btn_edit_profile)
        
        row = QHBoxLayout(); row.setSpacing(10); row.setContentsMargins(40,0,40,0)
        self.btn_comm_profile = QPushButton("0\nComments", styleSheet="background-color: #f9f9f9; border: 1px solid #eee; padding: 10px; border-radius: 5px; font-weight: bold; color: #555; margin: 0 40px;"); row.addWidget(self.btn_comm_profile)
        cl.addLayout(row)
        
        l.addWidget(c, 0, QtCore.Qt.AlignCenter); self.stack.addWidget(p)
        
    def updateProfileLabels(self, f, l, u, e): self.lbl_name_profile.setText(f"{f} {l}"); self.lbl_user_profile.setText(f"@{u}"); self.lbl_email_profile.setText(e); self.lbl_pfp.setText(f[0].upper())

    def createGameDetailsPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.setContentsMargins(0,0,0,0)
        top = QFrame(styleSheet="background-color: white; border-bottom: 1px solid #ddd;"); tb = QHBoxLayout(top); self.btn_back_gameDetails = QPushButton("← Back", styleSheet="border: none; font-weight: bold;"); tb.addWidget(self.btn_back_gameDetails); tb.addStretch(); l.addWidget(top)
        s = QScrollArea(styleSheet="background-color: transparent;", widgetResizable=True, frameShape=QFrame.NoFrame); w = QtWidgets.QWidget(); cl = QVBoxLayout(w); cl.setContentsMargins(40,30,40,40)
        h = QHBoxLayout(); h.setSpacing(30); self.gd_image = QLabel("IMG", alignment=QtCore.Qt.AlignCenter, styleSheet="background-color: #2c3e50; color: white; border-radius: 12px; min-width: 200px; min-height: 300px;"); h.addWidget(self.gd_image)
        d = QVBoxLayout(); d.setAlignment(QtCore.Qt.AlignTop); self.gd_title = QLabel("Title", styleSheet="font-size: 32px; font-weight: 800;"); d.addWidget(self.gd_title)
        self.gd_publisher = QLabel("Pub"); self.gd_genre = QLabel("Genre"); self.gd_size = QLabel("Size"); self.gd_price = QLabel("Price"); self.gd_sold = QLabel("Sold"); self.gd_revenue = QLabel("Revenue")
        for x in [self.gd_publisher, self.gd_genre, self.gd_size, self.gd_price, self.gd_sold, self.gd_revenue]: x.setStyleSheet("color: #555; font-size: 14px; margin-bottom: 2px;"); d.addWidget(x)
        self.btn_delete_game = QPushButton("DELETE GAME", styleSheet="background-color: #c0392b; color: white; font-weight: bold; padding: 10px; border-radius: 5px; margin-top: 20px;"); d.addWidget(self.btn_delete_game)
        h.addLayout(d); cl.addLayout(h)
        cl.addWidget(QLabel("Description:", styleSheet="font-weight:bold; margin-top:10px;")); self.gd_desc = QLabel("Desc", wordWrap=True); cl.addWidget(self.gd_desc)
        cl.addWidget(QLabel("Reviews:", styleSheet="font-size: 18px; font-weight: bold; margin-top: 20px; border-bottom: 1px solid #ccc;")); self.reviews_widget = QtWidgets.QWidget(); self.reviews_layout = QVBoxLayout(self.reviews_widget); cl.addWidget(self.reviews_widget); cl.addStretch()
        s.setWidget(w); l.addWidget(s); self.stack.addWidget(p)

    def createAdminReviewCard(self, user, text, rating, rid, gid, mw):
        c = QFrame(styleSheet="background-color: white; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 5px;"); hl = QHBoxLayout(c)
        lbl = QLabel(f"<b>{user}</b>: {text} ({rating}★)"); lbl.setWordWrap(True); lbl.setStyleSheet("color: #333;"); hl.addWidget(lbl, 1)
        btn = QPushButton("Delete", styleSheet="background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold; padding: 5px;"); btn.setFixedWidth(70); btn.clicked.connect(lambda ch: mw.deleteReviewFunc(rid, gid)); hl.addWidget(btn); return c

    def createGlobalReviewsPage(self):
        p = QtWidgets.QWidget(); l = QVBoxLayout(p); l.setContentsMargins(40,40,40,40)
        tb = QHBoxLayout(); self.btn_back_reviews = QPushButton("← Back", styleSheet="border:none; font-weight:bold; color: #2980b9; text-align: left;"); tb.addWidget(self.btn_back_reviews); tb.addStretch(); l.addLayout(tb)
        l.addWidget(QLabel("Global Review Manager", styleSheet="font-size: 24px; font-weight: bold; margin-bottom: 20px;"))
        s = QScrollArea(widgetResizable=True, frameShape=QtWidgets.QFrame.NoFrame); w = QtWidgets.QWidget(); self.global_reviews_layout = QVBoxLayout(w); self.global_reviews_layout.setAlignment(QtCore.Qt.AlignTop)
        s.setWidget(w); l.addWidget(s); self.stack.addWidget(p)

    def createGlobalReviewCard(self, user, game_title, text, rating, gid, rid, mw):
        c = QFrame(styleSheet="background-color: white; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 5px;"); hl = QHBoxLayout(c)
        info = QVBoxLayout(); info.addWidget(QLabel(f"<b>{user}</b> on <b>{game_title}</b>"))
        lbl_text = QLabel(f"{text} ({rating}★)"); lbl_text.setWordWrap(True); lbl_text.setStyleSheet("color:#555;"); info.addWidget(lbl_text); hl.addLayout(info, 1)
        btn = QPushButton("Delete", styleSheet="background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold; padding: 5px;"); btn.setFixedWidth(70); btn.clicked.connect(lambda ch: mw.deleteReviewFunc(rid, gid)); hl.addWidget(btn); return c
    
    def createHistoryPage(self):
        self.HistoryPage = QWidget(); l=QVBoxLayout(self.HistoryPage); l.setContentsMargins(40,40,40,40)
        self.btn_back_history = QPushButton("← Back", styleSheet="border:none; color:#2980b9; text-align:left; font-weight:bold"); l.addWidget(self.btn_back_history)
        l.addWidget(QLabel("Your Comments", styleSheet="font-size:22px; font-weight:bold")); s=QScrollArea(widgetResizable=True); w=QWidget(); self.history_layout=QVBoxLayout(w); self.history_layout.setAlignment(QtCore.Qt.AlignTop); s.setWidget(w); l.addWidget(s); self.stack.addWidget(self.HistoryPage)

    def populateHistory(self, posts, mw):
        self.clearLayout(self.history_layout)
        if not posts: self.history_layout.addWidget(QLabel("No comments."))
        for p in posts:
            f = QFrame(styleSheet="background-color: white; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 5px;"); l = QHBoxLayout(f)
            v = QVBoxLayout(); v.addWidget(QLabel(f"<b>{p['date']}</b>")); v.addWidget(QLabel(p['text'], styleSheet="color: #555;")); l.addLayout(v)
            btn = QPushButton("Delete", styleSheet="background-color: #e74c3c; color: white; font-weight: bold; border-radius: 5px; padding:5px;"); btn.setFixedWidth(60); 
            btn.clicked.connect(lambda ch, i=p['id']: mw.deletePostFunc(i)); l.addWidget(btn)
            self.history_layout.addWidget(f)

    def clearLayout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): self.clearLayout(item.layout())

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = AdminWindow()
    window.show()
    sys.exit(app.exec_())