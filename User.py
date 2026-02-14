import sys
import os  # REQUIRED FOR PATH FINDING
import datetime
import random
import re
import pyodbc
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QScrollArea, QLineEdit, QComboBox, QTextEdit, QGroupBox, QGridLayout, QDialog, QSplitter

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

    # --- PROFILE ---
    def fetch_user_info(self, user_id):
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
                    "password": getattr(row, 'User_Password', ''), "card": getattr(row, 'Card_Number', ''),
                    "balance": float(row.Wallet_Balance), "pfp_data": row.User_ProfilePic
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
        except: return False
        finally: conn.close()

    def update_profile_text(self, user_id, f, l, u, e, p, c):
        conn = self.get_connection()
        if not conn: return False
        try: 
            conn.cursor().execute("EXEC sp_UpdateUserProfile ?, ?, ?, ?, ?, ?, ?", (user_id, f, l, u, e, p, c))
            conn.commit()
            return True
        except: return False
        finally: conn.close()

    # --- GAMES & WISHLIST ---
    def fetch_store_games(self):
        conn = self.get_connection()
        if not conn: return {}
        games = {}
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetStoreGames")
            rows = cursor.fetchall()
            for row in rows:
                # --- UNIVERSAL IMAGE FETCH ---
                img_data = getattr(row, 'Game_Icon', None)
                if not img_data: img_data = getattr(row, 'Game_Image', None)
                if not img_data: img_data = getattr(row, 'Image', None)

                games[row.Game_ID] = {
                    "title": row.Title, 
                    "price": float(row.Price), 
                    "publisher": row.Publisher,
                    "genre": row.Genre, 
                    "size": f"{row.Size} GB", 
                    "downloads": f"{row.Downloads}",
                    "desc": row.Desc, 
                    "rating": float(row.Avg_Rating) if hasattr(row, 'Avg_Rating') and row.Avg_Rating else 0.0,
                    "image": img_data, 
                    "reviews": []
                }
        except Exception as e:
            print(f"Store Fetch Error: {e}")
        finally: conn.close()
        return games

    def fetch_user_library(self, user_id):
        conn = self.get_connection()
        if not conn: return set()
        owned = set()
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetUserLibrary ?", (user_id,))
            for row in cursor.fetchall(): 
                owned.add(row.Game_ID)
        finally: conn.close()
        return owned

    def fetch_user_wishlist(self, user_id):
        conn = self.get_connection()
        if not conn: return set()
        wished = set()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT Game_ID FROM WISHLIST WHERE User_ID = ?", (user_id,))
            for row in cursor.fetchall(): 
                wished.add(row.Game_ID)
        except: pass
        finally: conn.close()
        return wished

    def toggle_wishlist(self, user_id, game_id, add=True):
        conn = self.get_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            if add:
                cursor.execute("IF NOT EXISTS (SELECT 1 FROM WISHLIST WHERE User_ID=? AND Game_ID=?) INSERT INTO WISHLIST (User_ID, Game_ID) VALUES (?,?)", (user_id, game_id, user_id, game_id))
            else:
                cursor.execute("DELETE FROM WISHLIST WHERE User_ID=? AND Game_ID=?", (user_id, game_id))
            conn.commit()
        finally: conn.close()

    # --- HISTORY & COMMUNITY ---
    def fetch_user_reviews(self, uid):
        conn = self.get_connection()
        if not conn: return []
        data = []
        try: 
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetUserReviews ?", (uid,))
            for r in cursor.fetchall(): data.append(r)
        except: pass
        finally: conn.close()
        return data

    def fetch_user_comments(self, uid):
        conn = self.get_connection()
        if not conn: return []
        data = []
        try: 
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetUserComments ?", (uid,))
            for r in cursor.fetchall(): data.append(r)
        except: pass
        finally: conn.close()
        return data

    def delete_item(self, item_id, is_review=True):
        conn = self.get_connection()
        if not conn: return False
        proc = "sp_DeleteUserReview" if is_review else "sp_DeleteUserComment"
        try: 
            conn.cursor().execute(f"EXEC {proc} ?", (item_id,))
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
                posts.append({"user": row.Username, "role": row.User_Role, "text": row.Comment, "date": str(row.Comment_Date)})
        finally: conn.close()
        return posts

    def add_community_post(self, uid, txt):
        conn = self.get_connection()
        if not conn: return
        try: 
            conn.cursor().execute("EXEC sp_AddCommunityPost ?, ?", (uid, txt))
            conn.commit()
        finally: conn.close()

    # --- STORE ACTIONS ---
    def fetch_game_reviews(self, gid):
        conn = self.get_connection()
        if not conn: return []
        reviews = []
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_GetReviewsByGame ?", (gid,))
            for row in cursor.fetchall(): 
                reviews.append((row.Reviewer, row.Review_Text, row.Rating))
        finally: conn.close()
        return reviews

    def buy_game(self, uid, gid, amt):
        conn = self.get_connection()
        if not conn: return False
        try: 
            conn.cursor().execute("EXEC sp_BuyGame ?, ?, ?", (uid, gid, amt))
            conn.commit(); return True
        except: return False
        finally: conn.close()

    def add_review(self, uid, gid, r, t):
        conn = self.get_connection()
        if not conn: return
        try: 
            conn.cursor().execute("EXEC sp_AddReview ?, ?, ?, ?", (uid, gid, r, t))
            conn.commit()
        finally: conn.close()

    # --- DOWNLOAD GAME ---
    def download_game_file(self, game_id):
        conn = self.get_connection()
        if not conn: return None, None
        try:
            cursor = conn.cursor()
            cursor.execute("EXEC sp_DownloadGame ?", (game_id,))
            row = cursor.fetchone()
            if row and row.Game_FileData:
                return row.Game_name, row.Game_FileData
            return None, None
        except Exception as e:
            print(f"Download Error: {e}")
            return None, None
        finally: conn.close()

    def logout_user(self, user_id):
        conn = self.get_connection()
        if not conn: return
        try: 
            conn.cursor().execute("EXEC sp_UserLogout ?", (user_id,))
            conn.commit()
        except: pass
        finally: conn.close()

# --- MAIN WINDOW ---
class UserWindow(QtWidgets.QMainWindow):
    def __init__(self, user_data=None, db_config=None):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.db = DatabaseManager(db_config) # Initialize DB with config
        
        self.current_user = "Guest"
        self.user_db_id = None
        self.user_balance = 0.0
        self.user_full_info = {}

        if user_data:
            if hasattr(user_data, 'username'): self.current_user = user_data.username
            if hasattr(user_data, 'id'): self.user_db_id = user_data.id
            if hasattr(user_data, 'email'):
                real_id = self.db.get_user_id_by_email(user_data.email)
                if real_id: self.user_db_id = real_id
        
        if not self.user_db_id:
            print("ERROR: User ID not found. Attempting guest access.")

        self.current_review_game_id = None
        self.games_db = {}
        self.owned_games = set()
        self.wishlist_games = set()

        self.ui.setupUi(self, self.current_user)
        self.setWindowTitle(f"Retro Reload Store (ID: {self.user_db_id})") 
        
        # --- FIX: USE RESOURCE PATH FOR ICON ---
        self.setWindowIcon(QtGui.QIcon(resource_path('Icon.png')))
        
        if self.user_db_id:
            self.refreshAllData()
            
        self.setup_connections()

    def refreshAllData(self):
        info = self.db.fetch_user_info(self.user_db_id)
        if info:
            self.user_full_info = info
            self.user_balance = info['balance']
            self.ui.updateProfileUI(info)
            if info['pfp_data']:
                pixmap = QtGui.QPixmap()
                if pixmap.loadFromData(info['pfp_data']):
                    self.ui.pfp_label_profilePage.setPixmap(pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation))
                    self.ui.pfp_label_profilePage.setText("")

        self.games_db = self.db.fetch_store_games()
        self.owned_games = self.db.fetch_user_library(self.user_db_id)
        self.wishlist_games = self.db.fetch_user_wishlist(self.user_db_id)

        self.ui.refreshAllLists(self.games_db, self.owned_games, self.wishlist_games, self)
        self.loadCommunityFeed()
        self.loadHistoryPage()
        self.ui.refreshDashboard(self.games_db, self)

    def setup_connections(self):
        self.ui.btn_home.clicked.connect(lambda: self.ui.stack.setCurrentIndex(0))
        self.ui.btn_games.clicked.connect(lambda: self.ui.stack.setCurrentIndex(1))
        self.ui.btn_library.clicked.connect(lambda: self.ui.stack.setCurrentIndex(2))
        self.ui.btn_wishlist.clicked.connect(lambda: self.ui.stack.setCurrentIndex(3))
        self.ui.btn_search.clicked.connect(lambda: self.ui.stack.setCurrentIndex(4))
        self.ui.btn_community.clicked.connect(lambda: self.ui.stack.setCurrentIndex(5))
        self.ui.btn_profile.clicked.connect(lambda: self.ui.stack.setCurrentIndex(6))
        self.ui.btn_refresh.clicked.connect(self.refreshAllData)
        self.ui.btn_logout.clicked.connect(self.logoutFunc)
        
        self.ui.button_addComment.clicked.connect(self.addCommentFunc)
        self.ui.editProfile_btn.clicked.connect(self.openEditProfileDialog)
        self.ui.btn_change_pic.clicked.connect(self.changeProfilePicture)
        self.ui.submit_review_btn.clicked.connect(self.submitReviewFunc)
        self.ui.search_input.textChanged.connect(self.searchGames)

        self.ui.gamesCount_btn_profilePage.clicked.connect(lambda: self.ui.stack.setCurrentIndex(2)) 
        self.ui.commentsCount_btn_profilePage.clicked.connect(lambda: self.ui.stack.setCurrentIndex(7)) 
        
        self.ui.back_btn_gameView.clicked.connect(lambda: self.ui.stack.setCurrentIndex(1))
        self.ui.back_btn_gameReview.clicked.connect(lambda: self.ui.stack.setCurrentIndex(2))
        self.ui.back_btn_history.clicked.connect(lambda: self.ui.stack.setCurrentIndex(6))

    def searchGames(self, text):
        self.ui.clearLayout(self.ui.search_grid)
        if not text: return
        query = text.lower()
        row, col = 0, 0
        for gid, data in self.games_db.items():
            if data['title'].lower().startswith(query):
                card = self.ui.createCard(data, gid, self, "Store")
                self.ui.search_grid.addWidget(card, row, col)
                col += 1
                if col > 3: 
                    col = 0; row += 1

    def changeProfilePicture(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select Pic', 'c:\\', "Images (*.jpg *.png)")
        if fname:
            with open(fname, 'rb') as f: binary_data = f.read()
            if self.db.update_profile_pic(self.user_db_id, binary_data):
                self.refreshAllData()
                QMessageBox.information(self, "Success", "Picture Updated!")

    def toggleWishlist(self, gid):
        is_in_wishlist = gid in self.wishlist_games
        self.db.toggle_wishlist(self.user_db_id, gid, not is_in_wishlist)
        if is_in_wishlist: 
            self.wishlist_games.remove(gid)
            QMessageBox.information(self, "Wishlist", "Removed from Wishlist.")
        else:
            self.wishlist_games.add(gid)
            QMessageBox.information(self, "Wishlist", "Added to Wishlist!")
        self.ui.refreshAllLists(self.games_db, self.owned_games, self.wishlist_games, self)
        if self.ui.gv_btn_wishlist.isVisible():
             self.ui.gv_btn_wishlist.setText("Add" if gid not in self.wishlist_games else "Remove")

    def buyGameFunc(self, gid):
        if gid in self.owned_games: return
        g = self.games_db.get(gid)
        if self.user_balance < g['price']: 
            QMessageBox.warning(self, "Error", "Insufficient Funds")
            return
        if QMessageBox.question(self, "Buy", f"Buy {g['title']}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.buy_game(self.user_db_id, gid, g['price']):
                self.refreshAllData()
                self.ui.stack.setCurrentIndex(2)
                QMessageBox.information(self, "Success", "Game Purchased!")

    def downloadGameFunc(self, gid):
        name, data = self.db.download_game_file(gid)
        if not data:
            QMessageBox.warning(self, "Error", "Game file not found on server.\n(The publisher may not have uploaded a file).")
            return
            
        fname, _ = QFileDialog.getSaveFileName(self, "Save Game", f"{name}.zip", "Game Files (*.zip *.exe *.rar)")
        if fname:
            try:
                with open(fname, 'wb') as f:
                    f.write(data)
                QMessageBox.information(self, "Success", f"{name} downloaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def openGameDetails(self, gid):
        g = self.games_db.get(gid)
        g['reviews'] = self.db.fetch_game_reviews(gid)
        
        self.ui.gv_title.setText(g['title'])
        self.ui.gv_price.setText(f"${g['price']}")
        self.ui.gv_publisher.setText(f"Publisher: {g['publisher']}")
        self.ui.gv_genre.setText(f"Genre: {g['genre']}")
        self.ui.gv_size.setText(f"Size: {g['size']}")
        self.ui.gv_downloads.setText(f"{g['downloads']} DLs")
        self.ui.gv_desc.setText(g['desc'])
        
        if g.get('image'):
            pix = QtGui.QPixmap()
            if pix.loadFromData(g['image']):
                self.ui.gv_image.setPixmap(pix.scaled(200, 300, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                self.ui.gv_image.setText("")
            else: self.ui.gv_image.setText(g['title'])
        else: self.ui.gv_image.setText(g['title'])
        
        try: self.ui.gv_btn_buy.clicked.disconnect()
        except: pass
        
        if gid in self.owned_games:
            self.ui.gv_btn_buy.setText("Download")
            self.ui.gv_btn_buy.setEnabled(True)
            self.ui.gv_btn_buy.setStyleSheet("background-color: #27ae60; color: white; border-radius: 8px; font-weight: bold; padding: 15px;")
            self.ui.gv_btn_buy.clicked.connect(lambda: self.downloadGameFunc(gid))
        else:
            self.ui.gv_btn_buy.setText("Buy Now")
            self.ui.gv_btn_buy.setEnabled(True)
            self.ui.gv_btn_buy.setStyleSheet("background-color: #2980b9; color: white; border-radius: 8px; font-weight: bold; padding: 15px;")
            self.ui.gv_btn_buy.clicked.connect(lambda: self.buyGameFunc(gid))

        try: self.ui.gv_btn_wishlist.clicked.disconnect()
        except: pass
        self.ui.gv_btn_wishlist.clicked.connect(lambda: self.toggleWishlist(gid))
        self.ui.gv_btn_wishlist.setText("Remove from Wishlist" if gid in self.wishlist_games else "Add to Wishlist")

        self.ui.clearLayout(self.ui.gv_reviews_layout)
        if not g['reviews']: self.ui.gv_reviews_layout.addWidget(QLabel("No reviews."))
        for u, t, r in g['reviews']: 
            self.ui.gv_reviews_layout.addWidget(self.createReviewCard(u, t, r))
        
        self.ui.stack.setCurrentIndex(8)

    def openGameReview(self, gid):
        self.current_review_game_id = gid
        g = self.games_db.get(gid)
        g['reviews'] = self.db.fetch_game_reviews(gid)
        
        self.ui.gr_title.setText(g['title'])
        self.ui.gr_publisher.setText(f"Publisher: {g['publisher']}")
        self.ui.gr_genre.setText(f"Genre: {g['genre']}")
        self.ui.gr_size.setText(f"Size: {g['size']}")
        self.ui.gr_downloads.setText(f"Downloads: {g['downloads']}")
        self.ui.gr_desc.setText(g['desc'])
        
        if g.get('image'):
            pix = QtGui.QPixmap()
            if pix.loadFromData(g['image']):
                self.ui.gr_image.setPixmap(pix.scaled(200, 300, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                self.ui.gr_image.setText("")
        else:
            self.ui.gr_image.setText(g['title'])
        
        try: self.ui.gr_btn_download.clicked.disconnect()
        except: pass
        self.ui.gr_btn_download.clicked.connect(lambda: self.downloadGameFunc(gid))

        self.ui.clearLayout(self.ui.gr_reviews_layout)
        for u, t, r in g['reviews']: 
            self.ui.gr_reviews_layout.addWidget(self.createReviewCard(u, t, r))
        
        self.ui.stack.setCurrentIndex(9)

    def submitReviewFunc(self):
        if not self.current_review_game_id: return
        t = self.ui.review_input.toPlainText().strip()
        if not t: return
        r = int(self.ui.rating_combo.currentText()[0])
        self.db.add_review(self.user_db_id, self.current_review_game_id, r, t)
        QMessageBox.information(self, "Success", "Review Posted!")
        self.openGameReview(self.current_review_game_id)

    def createReviewCard(self, u, t, r):
        c = QFrame()
        c.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 5px;")
        l = QHBoxLayout(c)
        
        lbl_img = QLabel(u[0])
        lbl_img.setAlignment(QtCore.Qt.AlignCenter)
        lbl_img.setFixedSize(40,40)
        lbl_img.setStyleSheet("background-color:#3498db; color:white; border-radius:20px;")
        l.addWidget(lbl_img)
        
        v = QVBoxLayout()
        v.addWidget(QLabel(f"{u}  <span style='color:#f1c40f'>{'★'*r}</span>"))
        v.addWidget(QLabel(t, styleSheet="color:#555"))
        l.addLayout(v)
        return c

    def addCommentFunc(self):
        t = self.ui.addText_community.toPlainText().strip()
        if t: 
            self.db.add_community_post(self.user_db_id, t)
            self.loadCommunityFeed()
            self.ui.addText_community.clear()

    def loadCommunityFeed(self):
        self.ui.clearLayout(self.ui.community_layout)
        for p in self.db.fetch_community_feed():
            self.ui.community_layout.addWidget(self.createCommentCard(p))

    def createCommentCard(self, p):
        c = QFrame()
        c.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 5px;")
        l = QHBoxLayout(c)
        bg = "#e67e22" if p['role']=='Publisher' else ("#c0392b" if p['role']=='Admin' else "#3498db")
        
        lbl = QLabel(p['user'][0])
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setFixedSize(40,40)
        lbl.setStyleSheet(f"background-color:{bg}; color:white; border-radius:20px;")
        l.addWidget(lbl)
        
        v = QVBoxLayout()
        v.addWidget(QLabel(f"<b>{p['user']}</b> <span style='color:gray; font-size:10px;'>{p['date']}</span>"))
        v.addWidget(QLabel(p['text']))
        l.addLayout(v)
        return c

    def loadHistoryPage(self):
        self.ui.clearLayout(self.ui.history_reviews_layout)
        reviews = self.db.fetch_user_reviews(self.user_db_id)
        if not reviews: 
            self.ui.history_reviews_layout.addWidget(QLabel("No reviews yet."))
        for r in reviews:
            self.ui.history_reviews_layout.addWidget(self.createHistoryCard(r[0], f"{r[1]} ({r[2]}★)", r[3], True))

        self.ui.clearLayout(self.ui.history_comments_layout)
        comments = self.db.fetch_user_comments(self.user_db_id)
        if not comments: 
            self.ui.history_comments_layout.addWidget(QLabel("No comments yet."))
        for c in comments:
            self.ui.history_comments_layout.addWidget(self.createHistoryCard(c[0], "Community Post", c[1], False))

    def createHistoryCard(self, item_id, header, body, is_review):
        f = QFrame()
        f.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 5px;")
        l = QHBoxLayout(f)
        v = QVBoxLayout()
        v.addWidget(QLabel(f"<b>{header}</b>"))
        v.addWidget(QLabel(str(body), styleSheet="color: #555;"))
        l.addLayout(v)
        btn = QPushButton("Delete")
        btn.setFixedWidth(60)
        btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; border-radius: 5px;")
        btn.clicked.connect(lambda: self.deleteHistoryItem(item_id, is_review))
        l.addWidget(btn)
        return f

    def deleteHistoryItem(self, item_id, is_review):
        if QMessageBox.question(self, "Delete", "Delete this item?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.delete_item(item_id, is_review):
                self.loadHistoryPage()
                QMessageBox.information(self, "Success", "Deleted.")

    def openEditProfileDialog(self):
        d = QDialog(self)
        d.setWindowTitle("Edit")
        d.setFixedSize(300, 500)
        l = QVBoxLayout(d)
        
        def add_field(lbl, val):
            l.addWidget(QLabel(lbl))
            le = QLineEdit(str(val) if val else "")
            l.addWidget(le)
            return le

        ef = add_field("First Name", self.user_full_info.get('fname'))
        el = add_field("Last Name", self.user_full_info.get('lname'))
        eu = add_field("Username", self.user_full_info.get('username'))
        ee = add_field("Email", self.user_full_info.get('email'))
        ec = add_field("Credit Card", self.user_full_info.get('card'))
        ep = add_field("Password", self.user_full_info.get('password'))
        ep.setEchoMode(QLineEdit.Password)

        btn = QPushButton("Save Changes")
        btn.clicked.connect(lambda: self.saveProfileFunc(d, ef.text(), el.text(), eu.text(), ee.text(), ep.text(), ec.text()))
        l.addWidget(btn)
        d.exec_()

    def saveProfileFunc(self, d, f, l, u, e, p, c):
        if self.db.update_profile_text(self.user_db_id, f, l, u, e, p, c):
            self.refreshAllData()
            d.accept()
            QMessageBox.information(self, "Success", "Profile Updated!")

    def logoutFunc(self): 
        if QMessageBox.question(self, "Logout", "Logout?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes: 
            self.db.logout_user(self.user_db_id)
            QtWidgets.QApplication.quit()

    def closeEvent(self, event):
        self.db.logout_user(self.user_db_id)
        event.accept()

# --- UI CLASS ---
class Ui_MainWindow(object):
    def setupUi(self, MainWindow, username):
        self.userName = username; self.mainWindow = MainWindow
        MainWindow.resize(1200, 720); MainWindow.setStyleSheet("QMainWindow { background-color: #f0f2f5; }")
        self.centralwidget = QWidget(MainWindow); self.createSidebar(self.centralwidget); self.createStack(self.centralwidget)
        self.createHomePage(); self.createGamesPage(); self.createLibraryPage(); self.createWishlistPage(); self.createSearchPage(); self.createCommunityPage(); self.createProfilePage(username); self.createUserCommentsPage(); self.createGameViewPage(); self.createGameReviewPage()
        MainWindow.setCentralWidget(self.centralwidget); self.stack.setCurrentIndex(0)

    def createSidebar(self, parent):
        f = QFrame(parent); f.setGeometry(0, 0, 180, 720); f.setStyleSheet("background-color: white; border-right: 1px solid #dcdcdc;")
        l = QVBoxLayout(f); l.setSpacing(10); l.setContentsMargins(10, 20, 10, 20)
        
        lbl_title = QLabel("RETRO\nRELOAD")
        lbl_title.setAlignment(QtCore.Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        l.addWidget(lbl_title)
        
        self.btn_home = self.navBtn("HOME"); l.addWidget(self.btn_home)
        self.btn_games = self.navBtn("GAMES"); l.addWidget(self.btn_games)
        self.btn_library = self.navBtn("LIBRARY"); l.addWidget(self.btn_library)
        self.btn_wishlist = self.navBtn("WISHLIST"); l.addWidget(self.btn_wishlist)
        self.btn_search = self.navBtn("SEARCH"); l.addWidget(self.btn_search)
        self.btn_community = self.navBtn("COMMUNITY"); l.addWidget(self.btn_community)
        self.btn_profile = self.navBtn("PROFILE"); l.addWidget(self.btn_profile)
        l.addStretch(); self.btn_refresh = self.navBtn("REFRESH DATA"); l.addWidget(self.btn_refresh); self.btn_logout = self.navBtn("LOGOUT"); l.addWidget(self.btn_logout)

    def navBtn(self, t):
        b = QPushButton(t); b.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor)); b.setStyleSheet("QPushButton { border: none; text-align: left; padding: 12px; color: #555; font-weight: bold; } QPushButton:hover { background-color: #f0f2f5; color: #000; font-weight: bold; border-radius: 5px; }"); return b
    def createStack(self, p): self.stack = QtWidgets.QStackedWidget(p); self.stack.setGeometry(181, 0, 1019, 720)
    
    def refreshAllLists(self, games, owned, wished, mw):
        self.clearLayout(self.games_grid); self.clearLayout(self.library_grid); self.clearLayout(self.wishlist_grid)
        idx_g, idx_l, idx_w = 0, 0, 0
        for gid, g in games.items():
            if gid not in owned:
                self.games_grid.addWidget(self.createCard(g, gid, mw, "Store"), idx_g//5, idx_g%5); idx_g+=1
                if gid in wished: self.wishlist_grid.addWidget(self.createCard(g, gid, mw, "Wishlist"), idx_w//5, idx_w%5); idx_w+=1
            else:
                self.library_grid.addWidget(self.createCard(g, gid, mw, "Library"), idx_l//5, idx_l%5); idx_l+=1

    # --- UPDATED CARD CREATION ---
    def createCard(self, data, gid, mw, mode):
        f = QFrame(); f.setFixedSize(180, 260); f.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd;")
        l = QVBoxLayout(f); l.setContentsMargins(10,10,10,10); l.setSpacing(5)
        
        img = QLabel()
        img.setAlignment(QtCore.Qt.AlignCenter)
        img.setStyleSheet("background-color: #ecf0f1; border-radius: 5px; min-height: 100px;")
        
        if data.get('image'):
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(data['image']):
                img.setPixmap(pixmap.scaled(160, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            else:
                img.setText("IMG")
        else:
            img.setText("IMG")
            
        l.addWidget(img)
        
        title = QLabel(data['title'])
        title.setStyleSheet("font-weight:bold; font-size:12px;")
        l.addWidget(title)
        
        # ADD EXTRA INFO FOR LIBRARY
        if mode == "Library":
            l.addWidget(QLabel(f"{data['genre']}", styleSheet="color:#7f8c8d; font-size:10px;"))
            l.addWidget(QLabel(f"{data['publisher']}", styleSheet="color:#7f8c8d; font-size:10px;"))
        
        l.addStretch()
        
        if mode == "Store" or mode == "Wishlist":
            l.addWidget(QLabel(f"${data['price']}", styleSheet="color: #27ae60; font-weight: bold;"))
            btn = QPushButton("Details", styleSheet="background-color: #2980b9; color: white; border-radius: 5px; padding: 5px;")
            btn.clicked.connect(lambda: mw.openGameDetails(gid)); l.addWidget(btn)
        else: # Library
            btn = QPushButton("Play / Review", styleSheet="background-color: #8e44ad; color: white; border-radius: 5px; padding: 5px;")
            btn.clicked.connect(lambda: mw.openGameReview(gid)); l.addWidget(btn)
        return f

    def refreshDashboard(self, games, mw):
        while self.featured_layout.count(): item = self.featured_layout.takeAt(0); item.widget().deleteLater()
        count = 0
        for gid, g in games.items():
            if count >= 3: break
            self.featured_layout.addWidget(self.createCard(g, gid, mw, "Store"))
            count += 1
        if count == 0: self.featured_layout.addWidget(QLabel("No games available yet."))

    def clearLayout(self, layout):
        while layout.count(): item = layout.takeAt(0); item.widget().deleteLater()

    # Page Creators
    def createHomePage(self): 
        self.Home = QWidget(); l = QVBoxLayout(self.Home); l.setContentsMargins(30, 30, 30, 30); l.setSpacing(25)
        
        # --- FIXED: ADDED BANNER IMAGE (WITH RESOURCE PATH) ---
        self.lbl_banner = QLabel()
        self.lbl_banner.setFixedHeight(215)
        self.lbl_banner.setScaledContents(True)
        pixmap = QtGui.QPixmap(resource_path("RETRO_RELOAD.png")) # Uses function to find image in Exe
        
        if not pixmap.isNull():
            self.lbl_banner.setPixmap(pixmap)
        else:
            # Fallback if image not found
            self.lbl_banner.setText("RETRO RELOAD") 
            self.lbl_banner.setAlignment(QtCore.Qt.AlignCenter)
            self.lbl_banner.setStyleSheet("background-color: #2c3e50; color: white; border-radius: 15px; font-size: 24px; font-weight: bold;")
        
        l.addWidget(self.lbl_banner)
        
        lbl_feat = QLabel("Most Famous Games") 
        lbl_feat.setStyleSheet("font-size: 20px; font-weight: bold; margin-top: 10px;")
        l.addWidget(lbl_feat)
        # ------------------------------------------------
        
        # Featured Games Row
        content = QHBoxLayout()
        d_frame = QFrame(); d_frame.setFixedWidth(280); d_frame.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ddd;")
        dl = QVBoxLayout(d_frame)
        dl.addWidget(QLabel("Discounts"))
        self.discountScrole_homepage = QScrollArea(); self.discountScrole_homepage.setWidgetResizable(True); self.discountScrole_homepage.setFrameShape(QFrame.NoFrame)
        w = QWidget(); vl = QVBoxLayout(w)
        for i in range(1,11): vl.addWidget(QLabel(f"Game {i} - 50% OFF"))
        vl.addStretch(); self.discountScrole_homepage.setWidget(w); dl.addWidget(self.discountScrole_homepage); content.addWidget(d_frame)
        
        self.featured_layout = QHBoxLayout(); self.featured_layout.setSpacing(20)
        content.addLayout(self.featured_layout)
        l.addLayout(content); self.stack.addWidget(self.Home)

    def createGamesPage(self): 
        self.Games = QWidget(); l=QVBoxLayout(self.Games)
        l.addWidget(QLabel("STORE", styleSheet="font-size:24px; font-weight:bold"))
        s=QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame)
        w=QWidget(); self.games_grid=QGridLayout(w); s.setWidget(w)
        l.addWidget(s); self.stack.addWidget(self.Games)
        
    def createLibraryPage(self): 
        self.Library = QWidget(); l=QVBoxLayout(self.Library)
        l.addWidget(QLabel("LIBRARY", styleSheet="font-size:24px; font-weight:bold"))
        s=QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame)
        w=QWidget(); self.library_grid=QGridLayout(w); s.setWidget(w)
        l.addWidget(s); self.stack.addWidget(self.Library)
        
    def createWishlistPage(self): 
        self.Wishlist = QWidget(); l=QVBoxLayout(self.Wishlist)
        l.addWidget(QLabel("WISHLIST", styleSheet="font-size:24px; font-weight:bold"))
        s=QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame)
        w=QWidget(); self.wishlist_grid=QGridLayout(w); s.setWidget(w)
        l.addWidget(s); self.stack.addWidget(self.Wishlist)
        
    def createSearchPage(self): 
        self.Search = QWidget()
        l = QVBoxLayout(self.Search)
        l.setContentsMargins(30, 30, 30, 30)
        
        l.addWidget(QLabel("SEARCH GAMES", styleSheet="font-size:24px; font-weight:bold; color:#2c3e50"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search...")
        self.search_input.setStyleSheet("padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 14px;")
        l.addWidget(self.search_input)
        
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setFrameShape(QFrame.NoFrame)
        w = QWidget()
        self.search_grid = QGridLayout(w)
        self.search_grid.setSpacing(20)
        self.search_grid.setAlignment(QtCore.Qt.AlignTop)
        s.setWidget(w)
        l.addWidget(s)
        self.stack.addWidget(self.Search)
    
    def createCommunityPage(self):
        self.Community = QWidget()
        l = QVBoxLayout(self.Community)
        l.setContentsMargins(0, 0, 0, 0)

        # 1. Fancy Header
        header = QFrame()
        header.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2980b9, stop:1 #6dd5fa); border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;")
        header.setFixedHeight(120)
        hl = QVBoxLayout(header)
        hl.setContentsMargins(40, 20, 40, 20)
        
        lbl_title = QLabel("COMMUNITY HUB")
        lbl_title.setStyleSheet("font-size: 28px; font-weight: bold; color: white;")
        hl.addWidget(lbl_title)
        
        self.username_label_communityPage = QLabel(f"Posting as: {self.userName}")
        self.username_label_communityPage.setStyleSheet("font-size: 14px; color: #ecf0f1; font-style: italic;")
        hl.addWidget(self.username_label_communityPage)
        l.addWidget(header)

        # 2. Content Container
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 20, 40, 40)
        cl.setSpacing(20)

        # 3. Styled Input
        inp_frame = QFrame()
        inp_frame.setStyleSheet("background-color: white; border-radius: 15px; border: 1px solid #e0e0e0;")
        il = QVBoxLayout(inp_frame)
        il.setContentsMargins(15, 15, 15, 15)
        
        self.addText_community = QTextEdit()
        self.addText_community.setPlaceholderText("Share your thoughts...")
        self.addText_community.setMaximumHeight(80)
        self.addText_community.setStyleSheet("border: none; font-size: 14px;")
        il.addWidget(self.addText_community)
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.button_addComment = QPushButton("Post Update")
        self.button_addComment.setCursor(QtCore.Qt.PointingHandCursor)
        self.button_addComment.setStyleSheet("QPushButton { background-color: #2980b9; color: white; padding: 8px 20px; border-radius: 20px; font-weight: bold; } QPushButton:hover { background-color: #3498db; }")
        btn_row.addWidget(self.button_addComment)
        il.addLayout(btn_row)
        cl.addWidget(inp_frame)

        # 4. Feed
        cl.addWidget(QLabel("Recent Activity", styleSheet="font-size: 18px; font-weight: bold; color: #2c3e50; margin-top: 10px;"))
        s = QScrollArea()
        s.setFrameShape(QFrame.NoFrame)
        s.setWidgetResizable(True)
        s.setStyleSheet("background-color: transparent;")
        
        w = QWidget()
        w.setStyleSheet("background-color: transparent;")
        self.community_layout = QVBoxLayout(w)
        self.community_layout.setAlignment(QtCore.Qt.AlignTop)
        self.community_layout.setSpacing(15)
        
        s.setWidget(w)
        cl.addWidget(s)
        
        l.addWidget(content)
        self.stack.addWidget(self.Community)

    def createProfilePage(self, u):
        self.Profile = QWidget(); l=QVBoxLayout(self.Profile); l.setContentsMargins(0,0,0,0); c=QFrame(); c.setFixedWidth(500); c.setStyleSheet("background-color:white; border-radius:15px;"); cl=QVBoxLayout(c)
        
        self.pfp_label_profilePage = QLabel(u[0])
        self.pfp_label_profilePage.setAlignment(QtCore.Qt.AlignCenter)
        self.pfp_label_profilePage.setFixedSize(100,100)
        self.pfp_label_profilePage.setStyleSheet("background-color:#2c3e50; color:white; border-radius:50px; font-size:40px;")
        cl.addWidget(self.pfp_label_profilePage, 0, QtCore.Qt.AlignCenter)
        
        cl.addWidget(QLabel(f"@{u}", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size:18px; font-weight:bold")); self.btn_change_pic = QPushButton("Change Pic", styleSheet="border:none; color:#2980b9"); cl.addWidget(self.btn_change_pic, 0, QtCore.Qt.AlignCenter)
        self.balance_label_profilePage = QLabel("Balance: $0.00", alignment=QtCore.Qt.AlignCenter, styleSheet="font-size:16px; color:green; font-weight:bold"); cl.addWidget(self.balance_label_profilePage)
        self.fname_label_profilePage = QLabel("Fname"); self.lname_label_profilePage = QLabel("Lname"); self.email_label_profilePage = QLabel("Email"); 
        for w in [self.fname_label_profilePage, self.lname_label_profilePage, self.email_label_profilePage]: w.setAlignment(QtCore.Qt.AlignCenter); cl.addWidget(w)
        self.editProfile_btn = QPushButton("Edit Profile", styleSheet="background-color:#2980b9; color:white; padding:10px;"); cl.addWidget(self.editProfile_btn)
        sl=QHBoxLayout(); self.gamesCount_btn_profilePage=QPushButton("Library"); self.commentsCount_btn_profilePage=QPushButton("History"); 
        for b in [self.gamesCount_btn_profilePage, self.commentsCount_btn_profilePage]: b.setStyleSheet("background-color:#f9f9f9; padding:10px;"); sl.addWidget(b)
        cl.addLayout(sl); l.addWidget(c, 0, QtCore.Qt.AlignCenter); self.stack.addWidget(self.Profile)

    def createUserCommentsPage(self): 
        self.UserComments = QWidget(); l = QVBoxLayout(self.UserComments); l.setContentsMargins(30,30,30,30)
        top = QHBoxLayout(); self.back_btn_history = QPushButton("← Back"); top.addWidget(self.back_btn_history); top.addStretch(); l.addLayout(top)
        
        split = QSplitter(QtCore.Qt.Horizontal)
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.addWidget(QLabel("My Reviews", styleSheet="font-weight:bold; font-size:18px;"))
        s1 = QScrollArea(); s1.setWidgetResizable(True); c1 = QWidget(); self.history_reviews_layout = QVBoxLayout(c1); self.history_reviews_layout.setAlignment(QtCore.Qt.AlignTop)
        s1.setWidget(c1); l1.addWidget(s1); split.addWidget(w1)
        
        w2 = QWidget(); l2 = QVBoxLayout(w2); l2.addWidget(QLabel("My Comments", styleSheet="font-weight:bold; font-size:18px;"))
        s2 = QScrollArea(); s2.setWidgetResizable(True); c2 = QWidget(); self.history_comments_layout = QVBoxLayout(c2); self.history_comments_layout.setAlignment(QtCore.Qt.AlignTop)
        s2.setWidget(c2); l2.addWidget(s2); split.addWidget(w2)
        
        l.addWidget(split); self.stack.addWidget(self.UserComments) 
    
    def createGameViewPage(self):
        self.GameView = QWidget(); l=QVBoxLayout(self.GameView); top=QHBoxLayout(); self.back_btn_gameView=QPushButton("Back"); top.addWidget(self.back_btn_gameView); top.addStretch(); l.addLayout(top)
        h=QHBoxLayout(); self.gv_image=QLabel("IMG", alignment=QtCore.Qt.AlignCenter, styleSheet="background-color:#2c3e50; color:white; min-width:200px; min-height:300px"); h.addWidget(self.gv_image)
        d=QVBoxLayout(); self.gv_title=QLabel("Title", styleSheet="font-size:32px; font-weight:bold"); self.gv_publisher=QLabel("Pub"); self.gv_genre=QLabel("Genre"); self.gv_size=QLabel("Size"); self.gv_downloads=QLabel("DLs"); self.gv_price=QLabel("Price", styleSheet="font-size:24px; color:green"); self.gv_btn_buy=QPushButton("Buy"); self.gv_btn_wishlist=QPushButton("Wishlist", styleSheet="background-color:#f39c12; color:white; padding:10px; border-radius:5px")
        d.addWidget(self.gv_title); d.addWidget(self.gv_publisher); d.addWidget(self.gv_genre); d.addWidget(self.gv_size); d.addWidget(self.gv_downloads); d.addWidget(self.gv_price); d.addWidget(self.gv_btn_buy); d.addWidget(self.gv_btn_wishlist); d.addStretch(); h.addLayout(d); l.addLayout(h)
        self.gv_desc=QLabel("Desc", wordWrap=True); l.addWidget(self.gv_desc); l.addWidget(QLabel("Reviews:", styleSheet="font-weight:bold")); s=QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame); w=QWidget(); self.gv_reviews_layout=QVBoxLayout(w); s.setWidget(w); l.addWidget(s); self.stack.addWidget(self.GameView)

    def createGameReviewPage(self):
        self.GameReview = QWidget(); l=QVBoxLayout(self.GameReview); top=QHBoxLayout(); self.back_btn_gameReview=QPushButton("Back"); top.addWidget(self.back_btn_gameReview); top.addStretch(); l.addLayout(top)
        h=QHBoxLayout(); self.gr_image=QLabel("IMG", alignment=QtCore.Qt.AlignCenter, styleSheet="background-color:#2c3e50; color:white; min-width:200px; min-height:300px"); h.addWidget(self.gr_image)
        
        # --- FIXED: ADDED LABELS TO CLASS SO THEY CAN BE UPDATED ---
        d=QVBoxLayout()
        self.gr_title=QLabel("Title", styleSheet="font-size:32px; font-weight:bold")
        self.gr_publisher=QLabel("Pub")
        self.gr_genre=QLabel("Genre")
        self.gr_size=QLabel("Size")
        self.gr_downloads=QLabel("DLs")
        self.gr_desc=QLabel("Desc", wordWrap=True)
        
        # --- NEW: ADD DOWNLOAD BUTTON HERE ---
        self.gr_btn_download = QPushButton("DOWNLOAD GAME")
        self.gr_btn_download.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 12px; border-radius: 8px; font-size: 14px;")
        self.gr_btn_download.setCursor(QtCore.Qt.PointingHandCursor)
        
        d.addWidget(self.gr_title)
        d.addWidget(self.gr_publisher)
        d.addWidget(self.gr_genre)
        d.addWidget(self.gr_size)
        d.addWidget(self.gr_downloads)
        
        d.addSpacing(10)
        d.addWidget(self.gr_btn_download) # Add Download button to layout
        d.addStretch()
        h.addLayout(d)
        l.addLayout(h)
        l.addWidget(self.gr_desc)
        
        grp=QGroupBox("Review"); gl=QVBoxLayout(grp); rr=QHBoxLayout(); self.rating_combo=QComboBox(); self.rating_combo.addItems(["5","4","3","2","1"]); rr.addWidget(QLabel("Rating:")); rr.addWidget(self.rating_combo); rr.addStretch(); gl.addLayout(rr); self.review_input=QTextEdit(); self.review_input.setMaximumHeight(80); gl.addWidget(self.review_input); self.submit_review_btn=QPushButton("Submit"); gl.addWidget(self.submit_review_btn); l.addWidget(grp)
        s=QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame); w=QWidget(); self.gr_reviews_layout=QVBoxLayout(w); s.setWidget(w); l.addWidget(s); self.stack.addWidget(self.GameReview)

    def updateProfileUI(self, i):
        self.fname_label_profilePage.setText(i['fname']); self.lname_label_profilePage.setText(i['lname']); self.email_label_profilePage.setText(i['email']); self.balance_label_profilePage.setText(f"Balance: ${i['balance']:.2f}")

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = UserWindow()
    window.show()
    sys.exit(app.exec_())