import datetime
import threading 
from flask import jsonify, session
 
import requests
import email
import flask_sqlalchemy
import os
import sqlite3
import werkzeug.utils
import flask
import werkzeug.security
import functools

app = flask.Flask(__name__)
app.config['SESSION_PERMANENT'] = False

# 1. First, configure the database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'

# 2. Second, create the 'db' object
database = flask_sqlalchemy.SQLAlchemy(app)
app.secret_key = 'whatisagreatsecretkey'
def send_telegram_notification(message):
    token = "8557935362:AAFqUJHxyWNjxR04zc_6QHKtX9wH0ctyIk4"
    chat_id = "1229731360"  # The ID you got from @userinfobot
    url = f"https://api.telegram.org/bot{token}/sendMessage"
   
    data = {
        "chat_id": chat_id, "text": message, "parse_mode": "HTML"}
     
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram Error: {e}")

app.config['USE_SESSION_COOKIES'] = True
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = 'inventory.db'
DB_PATH = os.path.join(BASE_DIR, "inventory.db")
def get_db(): 
    db= getattr(flask.g, '_database', None)
    if db is None:
        db = flask.g._database = sqlite3.connect(DATABASE)
        # ADD THIS LINE BELOW:
        db.row_factory = sqlite3.Row
    return db
def init_db():
    with app.app_context():
        db = get_db()
        # Create Catalogues Table
        db.execute('''CREATE TABLE IF NOT EXISTS catalogues (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL)''')
        
        # Create s Table
        db.execute('''CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        price REAL DEFAULT 0.0,
                        stock INTEGER DEFAULT 0,
                        image_path TEXT,
                        catalogue_id INTEGER,
                        FOREIGN KEY (catalogue_id) REFERENCES catalogues (id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS staff (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        role TEXT,
                        phone TEXT,
                        email TEXT)''')
        
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
         
        print("Database initialized - 'users' table created!")
        db.execute(''' CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                total_price REAL NOT NULL,
                sold_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
)
                   ''')
        # Run this once in your index route to reset the table
    db.execute('DROP TABLE IF EXISTS notifications')
    db.execute('''
    CREATE TABLE notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
 
    db.commit()
        
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in flask.session:

            return flask.redirect(flask.url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
def log_notification(message, msg_type="info"):
    db = get_db()
    db.execute('INSERT INTO notifications (message, type) VALUES (?, ?)', 
               (message, msg_type))
    db.commit()
class Notification(database.Model):  # <--- This 'Notification' is your Model Name
     
    id = database.Column(database.Integer, primary_key=True)
    message = database.Column(database.Text, nullable=False)
    type = database.Column(database.String(50))
    created_at = database.Column(database.DateTime, default=database.func.current_timestamp())
     
@app.route('/notifications')
@login_required
def all_notifications():
    all_notes = Notification.query.order_by(Notification.created_at.desc()).all()
    for note in all_notes:
        # 2. Ensure created_at is a datetime object
        dt = note.created_at
        
        # 3. Add the 3-hour offset
        local_dt = dt + datetime.timedelta(hours=3)
        
        # 4. ATTACH it to the object so the template can see it
        # This fixes the "has no attribute 'display_time'" error
        setattr(note, 'display_time', local_dt)
    
    return flask.render_template('notifications.html', all_notes=all_notes)
@app.route('/sell_product_manual/<int:id>', methods=['POST'])
@login_required
def sell_product_manual(id):
    db = get_db()
    # Get the quantity from the form
    qty_sold = int(flask.request.form.get('quantity', 0))
    product = db.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    if product and product['stock'] >= qty_sold:
        new_stock = product['stock'] - qty_sold
        # Update Database
        db.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, id))
        total_sale_value = qty_sold * product['price']
        db.execute('''
            INSERT INTO sales (product_id, quantity, total_price) 
            VALUES (?, ?, ?)
        ''', (id, qty_sold, total_sale_value))
        db.commit()
        new_log = Notification(
        message=f"{qty_sold} Units of {product['name']} was sold.",
        type="product_sale")
         
        database.session.add(new_log)
        database.session.commit()
        # Prepare Telegram Notification
        user = flask.session.get('username', 'Admin')
        now = datetime.datetime.now().strftime("%I:%M %p, %b %d, %Y")
        
        msg = (f"<b>💰Sale Recorded</b>\n"
               f"<b>Item:</b> {product['name']}\n"
               f"<b>Quantity Sold:</b> {qty_sold}\n"
               f"<b>Remaining Stock:</b> {new_stock}\n"
               f"<b>Sold by:</b> {user}\n"
               f"<b>Time:</b> {now}")
        threading.Thread(target=send_telegram_notification, args=(msg,)).start()
    return flask.redirect(flask.url_for('products'))


@app.route('/notifications/count')
@login_required
def get_notification_count():
    try:
        # Just count EVERY row in the table, no filters.
        # If this works, the problem is your 'is_read' or 'user_id' columns.
        total_notes = Notification.query.count()
        return flask.jsonify({'count': total_notes})
    except Exception as e:
        # This will tell us if the table itself is missing or named wrong
        print(f"CRITICAL DB ERROR: {e}")
        return flask.jsonify({'count': 0})
@app.route('/')
@login_required
def index():       
    db = get_db()
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            sold_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    db.commit()

    #def get_stats(que# 1. Ensure Table Existsry, params=()):
    def get_stats(query, params=()):
        data = db.execute(query, params).fetchone()
        return {
            'qty': data['total_qty'] if data and data['total_qty'] else 0,
            'money': data['total_earnings'] if data and data['total_earnings'] else 0
        }
    # Today
    today_stats = get_stats('SELECT SUM(quantity) as total_qty, SUM(total_price) as total_earnings FROM sales WHERE date(sold_at) = date("now", "localtime")')
    
    # Weekly (Last 7 Days)
    weekly_stats = get_stats('SELECT SUM(quantity) as total_qty, SUM(total_price) as total_earnings FROM sales WHERE date(sold_at) >= date("now", "-7 days", "localtime")')
    
    # Monthly (Last 30 Days)
    monthly_stats = get_stats('SELECT SUM(quantity) as total_qty, SUM(total_price) as total_earnings FROM sales WHERE date(sold_at) >= date("now", "-30 days", "localtime")')
    
    # Yearly (Last 365 Days)
    yearly_stats = get_stats('SELECT SUM(quantity) as total_qty, SUM(total_price) as total_earnings FROM sales WHERE date(sold_at) >= date("now", "-365 days", "localtime")')
    
    # All Time
    all_time_stats = get_stats('SELECT SUM(quantity) as total_qty, SUM(total_price) as total_earnings FROM sales')

    # 3. Fetch Recent Sales, Products, etc. (Keep your existing code)
    recent_sales = db.execute('''
    SELECT s.quantity, s.total_price, s.sold_at, p.name 
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE date(s.sold_at) = date('now', 'localtime')
    ORDER BY s.sold_at DESC
''').fetchall()
    
    # 1. Fetch from DB
    recent_sales_raw = db.execute('''
        SELECT s.quantity, s.total_price, s.sold_at, p.name 
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE date(s.sold_at) = date('now', 'localtime')
        ORDER BY s.sold_at DESC
    ''').fetchall()

    recent_sales = []
    for sale in recent_sales_raw:
        item = dict(sale)
        
        # 1. Parse the UTC time from the database
        dt_utc = datetime.datetime.strptime(item['sold_at'], '%Y-%m-%d %H:%M:%S')
        
        # 2. MANUALLY add 3 hours (This bypasses all timezone detection issues)
        dt_local = dt_utc + datetime.timedelta(hours=3)
        
        # 3. Create the pretty string
        item['pretty_time'] = dt_local.strftime('%I:%M %p')
        
        recent_sales.append(item)

    # 3. Send the list we just built (recent_sales) to the template
     
    prods = db.execute('''
        SELECT p.*, c.name AS cat_name 
        FROM products p 
        LEFT JOIN catalogues c ON p.catalogue_id = c.id
    ''').fetchall()
    
    products_list = [dict(row) for row in prods]
    cats = db.execute('SELECT * FROM catalogues').fetchall()
    
    low_stock_list = [p for p in products_list if 0 < (p['stock'] or 0) < 20]
    out_of_stock_list = [p for p in products_list if (p['stock'] or 0) == 0]

    # 4. PASS ALL TO HTML
    return flask.render_template('index.html', 
                           sales_today=today_stats['qty'],
                           daily_earnings=today_stats['money'],
                           weekly_earnings=weekly_stats['money'],
                           monthly_earnings=monthly_stats['money'],
                                                                                                    yearly_earnings=yearly_stats['money'],
                           all_time_earnings=all_time_stats['money'],
                           recent_sales=recent_sales,
                           products_list=products_list,
                           total_cats=len(cats),
                           low_stock=len(low_stock_list), 
                           out_of_stock=len(out_of_stock_list),
                           total_prods=len(products_list),
                           total_stock=sum(p['stock'] or 0 for p in products_list))
    
# The following code block was outside of any function and caused a syntax error.
# It has been removed to fix the "return" outside function error.
@app.route('/notifications')
@login_required
def notifications_page():
    db = get_db()
    # Get every notification ever recorded, newest first
    all_notes = db.execute('SELECT * FROM notifications ORDER BY created_at DESC').fetchall()
    return flask.render_template('notifications.html', all_notes=all_notes)
@app.route('/catalogues')
@login_required
def catalogues():
    db = get_db()
    
    # 1. Fetch Categories
    cats = db.execute('SELECT * FROM catalogues').fetchall()
    
    # 2. Fetch Products
    prods = db.execute('SELECT * FROM products').fetchall()
    
    # 3. CRITICAL: Convert database rows into a list of dictionaries
    # This is what makes the data "JSON serializable"
    products_list = [dict(row) for row in prods]
    
    # 4. Pass BOTH to the template
    return flask.render_template('catalogues.html', 
                           catalogues=cats, 
                           products_list=products_list) # <--- Make sure this is here!

@app.route('/add_catalogue', methods=['POST'])
@login_required
def add_catalogue():
    name = flask.request.form['name']
    db = get_db()
    db.execute('INSERT INTO catalogues (name) VALUES (?)', (name,))
    db.commit()
    new_log = Notification(
    message=f"Catalogue {name} was added.",
    type="catalogue_addition"
     
)
    database.session.add(new_log)
    database.session.commit()
    now = datetime.datetime.now().strftime("%I:%M %p, %b %d, %Y ")
    user = flask.session.get('username', 'Admin')
    msg = (f"<b>New Catalogue Added</b>\n"
    f"<b>User:</b> {user}\n"
    f"<b>Catalogue:</b> {name}\n"
    f"<b>Time:</b> {now}")
    threading.Thread(target=send_telegram_notification, args=(msg,)).start()
    log_notification(f"📁 New Catalogue created: <b>{name}</b>", "category")
    return flask.redirect(flask.url_for('catalogues'))

# --- NEW: EDIT ROUTE ---
@app.route('/edit_catalogue/<int:id>', methods=['POST'])
@login_required
def edit_catalogue(id):
    db = get_db()
     
    new_name = flask.request.form.get('name').strip()
    
    # 1. FETCH OLD DATA FIRST (Before the update happens)
    old_catalogue = db.execute('SELECT name FROM catalogues WHERE id = ?', (id,)).fetchone()
    
    if not old_catalogue:
        return flask.redirect(flask.url_for('catalogues'))

    old_name = old_catalogue['name']

    try:
        # 2. PERFORM THE UPDATE (No extra comma before WHERE)
        db.execute('UPDATE catalogues SET name=? WHERE id=?', (new_name, id))
        db.commit()
        # 3. PREPARE NOTIFICATION
        now = datetime.datetime.now().strftime("%I:%M %p, %b %d %Y")
        user = flask.session.get('username', 'Admin')

        msg = (
                f"<b> Catalogue Updated</b>\n"
                 
                f"<b>Old Name:</b> {old_name}\n"
                f"<b>New Name:</b> {new_name}\n"
                 
                f"<b>Changes by:</b> {user}\n"
                f"<b>Time:</b> {now}"
            )

        # 4. SEND NOTIFICATION
        threading.Thread(target=send_telegram_notification, args=(msg,)).start()
        new_log = Notification(
        message=f"Catalogue {old_name} was updated to {new_name}.",
        type="catalogue_update"
        
        
          )
        database.session.add(new_log)
        database.session.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        flask.flash("Error: That catalogue name already exists.", "danger")
        print("Error: That catalogue name already exists.")
    log_notification(f"📁 Catalogue updated: <b>{new_name}</b>", "category")
    return flask.redirect(flask.url_for('catalogues'))

# --- NEW: DELETE ROUTE ---
@app.route('/delete_catalogue/<int:id>')
@login_required
def delete_catalogue(id):
    db = get_db()

    # 1. FETCH the name first while it still exists
    catalogue = db.execute('SELECT name FROM catalogues WHERE id = ?', (id,)).fetchone()
    
    if catalogue:
        cat_name = catalogue['name']
        
        # 2. NOW delete it
        db.execute('DELETE FROM catalogues WHERE id = ?', (id,))
        db.commit()
    new_log = Notification(
    message=f"Catalogue {cat_name} was deleted.",
    type="catalogue_deletion"
     
     )
    database.session.add(new_log)
    database.session.commit()
        # 3. Prepare the message
    now = datetime.datetime.now().strftime("%I:%M %p, %b %d, %Y")
    user = flask.session.get('username', 'Admin')

    msg = (
            f"<b> Catalogue Deleted</b>\n"
            f"<b>Catalogue:</b> {cat_name}\n"
            f"<b>Deleted by:</b> {user}\n"
            f"<b>Time:</b> {now}"
        )
        
        # 4. Send notification
    threading.Thread(target=send_telegram_notification, args=(msg,)).start()
    log_notification(f"🗑️ Catalogue <b>{cat_name}</b> was deleted", "warning")
    return flask.redirect(flask.url_for('catalogues'))
@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    db = get_db()
    
    if flask.request.method == 'POST':
        name = flask.request.form.get('name')
        price = flask.request.form.get('price')
        stock = flask.request.form.get('stock')
        image = flask.request.files.get('image')
        cat_name = flask.request.form.get('catalogue_name')
        new_log = Notification(
        message=f"Product {name} was added to stock.",
        type="product_addition"
        )
        database.session.add(new_log)
        database.session.commit()
         
        # 1. Check if the catalogue exists
        catalogue = db.execute('SELECT id FROM catalogues WHERE name = ?', (cat_name,)).fetchone()
        
        if catalogue:
            catalogue_id = catalogue['id']
        elif cat_name:
            # 2. If it's a NEW name, create the catalogue first
            cursor = db.execute('INSERT INTO catalogues (name) VALUES (?)', (cat_name,))
            db.commit()
            catalogue_id = cursor.lastrowid
        else:
            catalogue_id = None

        # 3. Insert the product (Notice the table name is "products")
        db.execute('''
            INSERT INTO products (name, price, stock, catalogue_id, image_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, price, stock, catalogue_id, image.filename if image else None))

        db.commit()

        now = datetime.datetime.now().strftime("%I:%M %p, %b %d, %Y ")
        user = flask.session.get('username', 'Admin')
        
        msg = (f"<b>New Product Added</b>\n"
        f"<b>User:</b> {user}\n"
        f"<b>Item:</b> {name}\n"
        f"<b>Stock:</b> {stock}\n"
        f"<b>Price:</b> {price}\n"
        f"<b>Catalogue:</b> {cat_name}\n"
        f"<b>Time:</b> {now}")

        threading.Thread(target=send_telegram_notification, args=(msg,)).start()
        return flask.redirect(flask.url_for('products'))
    
    query = '''
        SELECT p.*, c.name AS catalogue_name 
        FROM products p
        LEFT JOIN catalogues c ON p.catalogue_id = c.id
    '''
    products_list = db.execute(query).fetchall()
    catalogues_list = db.execute('SELECT * FROM catalogues').fetchall()
     
    return flask.render_template('products.html', products=products_list, catalogues=catalogues_list)
    

    # ... (Rest of your GET logic to display the table) ...
@app.route('/edit_product/<int:id>', methods=['POST'])
@login_required
def edit_product(id):
    db = get_db()
    
    old_query = '''
        SELECT p.*, c.name AS cat_name 
        FROM products p 
        LEFT JOIN catalogues c ON p.catalogue_id = c.id 
        WHERE p.id = ?
    '''
    old_product = db.execute(old_query, (id,)).fetchone()

    if not old_product:
         
        return flask.redirect(flask.url_for('products'))

    # 2. Get data from the form
    new_name = flask.request.form.get('name')
    new_stock = flask.request.form.get('stock')
    new_price = flask.request.form.get('price')
    catalogue_id = flask.request.form.get('catalogue_id')

    # Convert to dict for safe access
    old_data = dict(old_product)

    # Get OLD catalogue name (from the joined query)
    old_cat_name = old_data.get('cat_name') or 'None'

    # Get NEW catalogue name 
    # (You can improve this later by joining or querying the new name)
    new_cat_name = 'None'
    if catalogue_id:
        new_cat = db.execute('SELECT name FROM catalogues WHERE id = ?', (catalogue_id,)).fetchone()
        if new_cat:
            new_cat_name = new_cat['name']

    # 3. Update the product in database
    db.execute('''
        UPDATE products 
        SET name=?, price=?, stock=?, catalogue_id=? 
        WHERE id=?
    ''', (new_name, new_price, new_stock, catalogue_id, id))
    db.commit()
     
    # 4. Device & User info
    platform = (flask.request.user_agent.platform or "Device").capitalize()
    browser = (flask.request.user_agent.browser or "Browser").capitalize()
    display_source = f"{platform} ({browser})"
    db.execute('UPDATE products SET name=?, price=?, stock=?, catalogue_id=? WHERE id=?', 
               (new_name, new_price, new_stock, catalogue_id, id))
    db.commit()
    now = datetime.datetime.now().strftime("%I:%M %p, %b %d, %Y ")
    user = flask.session.get('username', 'Admin')
     # 5. Build the notification message
    msg = (
        f"<b>Product Updated</b>\n"
        f"<b>Item:</b> {old_data.get('name', 'Unknown')} → {new_name}\n"
        f"<b>Stock:</b> {old_data.get('stock', 0)} → {new_stock}\n"
        f"<b>Price:</b> {old_data.get('price', 0)} → {new_price}\n"
        f"<b>Catalogue:</b> {old_cat_name} → {new_cat_name}\n"
        f"<b>Changes by:</b> {user}\n"
        f"<b>Time:</b> {now}"
    )
    new_log = Notification(
    message=f"Product {new_name} was updated to {old_data.get('name', 'unknown')}.",
    type="product_update"
    
)
    database.session.add(new_log)
    database.session.commit()
    # Send notification in background
    threading.Thread(target=send_telegram_notification, args=(msg,)).start()

    log_notification(f"✏️ Product updated: <b>{new_name}</b>", "product")
    return flask.redirect(flask.url_for('products'))
@app.route('/delete_product/<int:id>')
@login_required
def delete_product(id):
    db = get_db()
    product= flask.request.form.get('product_name')
    # Get product details INCLUDING catalogue name BEFORE deleting
    query = '''
        SELECT p.name AS product_name, 
               c.name AS cat_name
        FROM products p
        LEFT JOIN catalogues c ON p.catalogue_id = c.id
        WHERE p.id = ?
    '''
    
    product = db.execute(query, (id,)).fetchone()

    if not product:
         
        return flask.redirect(flask.url_for('products'))

    # Extract names
    product_name = product['product_name']
    cat_name = product['cat_name'] or 'Uncategorized'
    new_log = Notification(
    message=f"Product {product_name} was deleted.",
    type="product_deletion"
     
)
    
    database.session.add(new_log)
    database.session.commit()
    # Now delete the product
    db.execute('DELETE FROM products WHERE id = ?', (id,))
    db.commit()
     
    # Prepare notification message
    now = datetime.datetime.now().strftime("%I:%M %p, %b %d, %Y ")
    user = flask.session.get('username', 'Admin')

    msg = (
        f"<b>Product Deleted</b>\n"
        f"<b>Item:</b> {product_name}\n"
        f"<b>Catalogue:</b> {cat_name}\n"
        f"<b>Deleted by:</b> {user}\n"
        f"<b>Time:</b> {now}"
    )
    # Send notification (in background to avoid delaying redirect)
    threading.Thread(target=send_telegram_notification, args=(msg,)).start()
    log_notification(f"✏️ Product deleted: <b>{product_name}</b>", "product")
    return flask.redirect(flask.url_for('products'))
# 1. Protection Decorator
# Add @login_required above any route you want to protect
def trigger_inventory_report():
    # Only run if we haven't sent a report in this session yet
    if not flask.session.get('report_sent'):
        db = get_db()
        
        # 1. Fetch data using SQL queries since you don't have a model
        low_stock_items = db.execute(
            'SELECT name, stock FROM products WHERE stock > 0 AND stock < 20'
        ).fetchall()
        
        out_of_stock_items = db.execute(
            'SELECT name, stock FROM products WHERE stock <= 0'
        ).fetchall()

        # 2. Only build and send the report if there is something to report
        if low_stock_items or out_of_stock_items:
            now = datetime.datetime.now().strftime("%b %d %Y, %I:%M %p")
            report = f"<b>📊 Inventory Summary</b>\n<i>{now}</i>\n\n"

            if out_of_stock_items:
                report += "<b>🚨 OUT OF STOCK:</b>\n"
                for item in out_of_stock_items:
                    # Access by key name because fetchall() returns row objects
                    safe_name = item['name'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    report += f"• {safe_name}\n"
                report += "\n"

            if low_stock_items:
                report += "<b>⚠️ LOW STOCK (&lt;20):</b>\n" 
                for item in low_stock_items:
                    safe_name = item['name'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    report += f"• {safe_name} ({item['stock']} left)\n"

            # 3. Send to Telegram in a separate thread
            threading.Thread(target=send_telegram_notification, args=(report,)).start()
        
        # Set the flag so it doesn't send again until the next login
        flask.session['report_sent'] = True
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if flask.request.method == 'POST':
        db = get_db()
        name = flask.request.form.get('name')
        username = flask.request.form.get('username')
        email = flask.request.form.get('email')
        password = flask.request.form.get('password')
        
        # === Strong Validation First ===
        if not name or not username or not email or not password:
            flask.flash('All fields are required!', 'danger')
            return flask.render_template('signup.html')

        email = email.strip()
        if '@' not in email or '.' not in email:
            flask.flash('Please enter a valid email address!', 'danger')
            return flask.render_template('signup.html')

        if len(password) < 6:
            flask.flash('Password must be at least 6 characters long!', 'danger')
            return flask.render_template('signup.html')

        hashed_pw = werkzeug.security.generate_password_hash(password)

        try:
            # Check if username or email already exists
            existing = db.execute('''
                SELECT id FROM users 
                WHERE username = ? OR email = ?
            ''', (username, email)).fetchone()

            if existing:
                flask.flash('Username or email already exists!', 'danger')
                return flask.render_template('signup.html')

            # Insert the new user
            db.execute('''
                INSERT INTO users (username, name, email, password)
                VALUES (?, ?, ?, ?)
            ''', (username, name, email, hashed_pw))
            
            db.commit()

            # === Log the Notification ONLY after success ===
            new_log = Notification(
                message=f"User {username} Successfully Signed Up.",
                type="user_signup",
                created_at=datetime.datetime.now()
            )
            database.session.add(new_log)
            database.session.commit()

            flask.flash('Account created successfully!', 'success')
            return flask.redirect(flask.url_for('index'))

        except sqlite3.IntegrityError:
            db.rollback()
            flask.flash('Username or email already exists!', 'danger')
        except Exception as e:
            if 'db' in locals():
                db.rollback()
            flask.flash('An error occurred. Please try again.', 'danger')
            print("Signup error:", e)
        flask.session['username'] = username 
        
        # TRIGGER REPORT HERE
        trigger_inventory_report() 

        return flask.redirect(flask.url_for('index'))
    # This part runs for GET requests or if validation fails
    return flask.render_template('signup.html')
@app.before_request
def require_login():
    # List of pages that DO NOT need a login (Login and Signup)
    allowed_routes = ['login', 'signup', 'static']
    
    # If the user is trying to visit a protected page and isn't logged in...
    if flask.request.endpoint not in allowed_routes and 'user_id' not in flask.session:
        return flask.redirect(flask.url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    user = None
    app.config['SESSION_PERMANENT'] = False
    if flask.request.method == 'POST':
        username = flask.request.form['username']
        password = flask.request.form['password']
        user = get_db().execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        new_log = Notification(
        message=f"User {username} Successfully Logged In.",
        type="user_login"
      
)
        database.session.add(new_log)
        database.session.commit()
        
        if user and werkzeug.security.check_password_hash(user['password'], password):
            flask.session['user_id'] = user['id']
            flask.session['username'] = user['username']
            if not flask.session.get('report_sent'):
                trigger_inventory_report()
                flask.session['report_sent'] = True

            flask.flash("Logged in successfully!", "success")
            return flask.redirect(flask.url_for('index'))
        else:
            flask.flash("Invalid credentials", "error")
    
    
       # ← Add this line
    return flask.render_template('login.html')

@app.route('/logout')
def logout():
    flask.session.clear() # This wipes the memory
    return flask.redirect(flask.url_for('login'))

# 2. Apply it to your inventory
 
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
if __name__ == "__main__":
    init_db()  # This now runs safely inside the app context
    app.run(debug=True, use_reloader=False)

