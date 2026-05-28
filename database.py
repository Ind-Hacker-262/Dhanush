import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiosk.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Customer', 'ShopOwner', 'Sysadmin')),
        bank_account_number TEXT,
        bank_ifsc TEXT
    )
    ''')
    
    # 2. Create Products Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT,
        cost_price REAL NOT NULL,
        sale_price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        image_url TEXT,
        FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    # 3. Create Orders Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        shipping_address TEXT NOT NULL,
        total_original_price REAL NOT NULL,
        points_applied_discount REAL NOT NULL DEFAULT 0.0,
        final_amount_paid REAL NOT NULL,
        points_earned INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Shipped', 'Delivered')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    # 4. Create Order Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        purchase_price REAL NOT NULL,
        referral_user_id INTEGER,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (referral_user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    ''')
    
    # 5. Create Wallet Transactions Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS wallet_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        points_change INTEGER NOT NULL,
        description TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    # 6. Create Referrals Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        referrer_id INTEGER NOT NULL,
        code TEXT UNIQUE NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    
    # 7. Seed Accounts if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Seeding database with test users...")
        test_users = [
            ("Platform Admin", "admin@kiosk.com", "9999999999", generate_password_hash("admin123"), "Sysadmin", "98765432101", "SBIN0001234"),
            ("Star Merchant", "owner@kiosk.com", "8888888888", generate_password_hash("owner123"), "ShopOwner", "98765432102", "ICIC0005678"),
            ("Aman Sharma", "customer@kiosk.com", "7777777777", generate_password_hash("customer123"), "Customer", "98765432103", "HDFC0009876"),
            ("Rahul Kumar", "referee@kiosk.com", "6666666666", generate_password_hash("referee123"), "Customer", "98765432104", "BARB0MUMBAI")
        ]
        cursor.executemany('''
        INSERT INTO users (name, email, phone, password_hash, role, bank_account_number, bank_ifsc)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', test_users)
        conn.commit()
        
        # Add 150 start reward points to customer accounts for immediate testing
        cursor.execute("SELECT id FROM users WHERE email='customer@kiosk.com'")
        cust1_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE email='referee@kiosk.com'")
        cust2_id = cursor.fetchone()[0]
        
        cursor.execute("INSERT INTO wallet_transactions (user_id, points_change, description) VALUES (?, ?, ?)", (cust1_id, 150, "Welcome Bonus Points"))
        cursor.execute("INSERT INTO wallet_transactions (user_id, points_change, description) VALUES (?, ?, ?)", (cust2_id, 100, "Welcome Bonus Points"))
        conn.commit()

    # 8. Seed Sample Products if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        print("Seeding sample products...")
        cursor.execute("SELECT id FROM users WHERE role='ShopOwner' LIMIT 1")
        owner_id = cursor.fetchone()[0]
        
        sample_products = [
            (owner_id, "Wireless Headphones Pro", "Experience pure sound with active noise cancellation and 40-hour battery life.", "Electronics", 3200.0, 5499.0, 45, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500"),
            (owner_id, "Chronos Smartwatch X", "Vibrant AMOLED screen, heart rate tracking, Sleep monitoring, and GPS enabled.", "Wearables", 4800.0, 7999.0, 30, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500"),
            (owner_id, "Minimalist Leather Wallet", "Crafted from top-grain leather with RFID protective lining and slim card pockets.", "Accessories", 400.0, 999.0, 80, "https://images.unsplash.com/photo-1627124118303-622c97be5e88?w=500"),
            (owner_id, "Ergonomic Mesh Chair", "Adjustable lumbar comfort, heavy duty nylon base, and high-density foam padding.", "Furniture", 6500.0, 11499.0, 15, "https://images.unsplash.com/photo-1592078615290-033ee584e267?w=500"),
            (owner_id, "Smart Thermos Flask", "Double-walled vacuum insulated bottle with live LED temperature display cap.", "Kitchenware", 500.0, 1299.0, 60, "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=500")
        ]
        
        cursor.executemany('''
        INSERT INTO products (owner_id, name, description, category, cost_price, sale_price, stock, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_products)
        conn.commit()

    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
