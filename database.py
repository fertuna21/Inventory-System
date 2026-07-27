import sqlite3

def init_db():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Enable Foreign Key enforcement
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # 1. Catalogues
    cursor.execute('''CREATE TABLE IF NOT EXISTS catalogues 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT UNIQUE NOT NULL
                   )''')
    
    # 2. Products 
    # Added image_path and changed cat_id to catalogue_id to match your app logic
   
    cursor.execute('''CREATE TABLE IF NOT EXISTS products 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT NOT NULL, 
                       price REAL DEFAULT 0.0, 
                       stock INTEGER DEFAULT 0, 
                       image_path TEXT, 
                       catalogue_id INTEGER, 
                       FOREIGN KEY(catalogue_id) REFERENCES catalogues(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)''')
    cursor.execute
    ('''CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity INTEGER NOT NULL,
    total_price REAL NOT NULL,
    sold_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (product_id) REFERENCES products (id)

)''')
    # Run this once in your index route to reset the table
    cursor.execute('DROP TABLE IF EXISTS notifications')
    cursor.execute('''
    CREATE TABLE notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # 3. Staff Members
    cursor.execute('''CREATE TABLE IF NOT EXISTS staff 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT NOT NULL, 
                       role TEXT, 
                       phone TEXT,
                       email TEXT)''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == "__main__":
    init_db()