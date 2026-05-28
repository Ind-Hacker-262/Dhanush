from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import uuid
from database import get_db_connection, init_db
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Config file upload directories
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database on startup
init_db()

# --- Helper Functions ---
def get_user_points(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(points_change) FROM wallet_transactions WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()[0]
    conn.close()
    return res if res is not None else 0

def get_current_user():
    if 'user_id' not in session:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    return user

# --- Context Processors ---
@app.context_processor
def inject_user_stats():
    user = get_current_user()
    if user:
        points = get_user_points(user['id'])
        return dict(current_user=user, user_points=points, user_wallet_rs=round(points * 0.1, 2))
    return dict(current_user=None, user_points=0, user_wallet_rs=0.0)

# --- Routing ---

# 1. Login & Registration
@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next', '').strip()
    if 'user_id' in session:
        return redirect(next_page if next_page else url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']
        next_page = request.form.get('next', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['name']
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(next_page if next_page else url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template('login.html', next_page=next_page)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        password = request.form['password']
        role = request.form['role']
        bank_acc = request.form.get('bank_account', '').strip()
        bank_ifsc = request.form.get('bank_ifsc', '').strip()
        
        if not name or not email or not password or not phone:
            flash("Please fill in all required fields.", "danger")
            return render_template('register.html')
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("Email is already registered.", "danger")
            return render_template('register.html')
            
        password_hash = generate_password_hash(password)
        try:
            cursor.execute('''
            INSERT INTO users (name, email, phone, password_hash, role, bank_account_number, bank_ifsc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, email, phone, password_hash, role, bank_acc, bank_ifsc))
            conn.commit()
            
            # Give a small signup welcome bonus points
            new_user_id = cursor.lastrowid
            cursor.execute('''
            INSERT INTO wallet_transactions (user_id, points_change, description)
            VALUES (?, ?, ?)
            ''', (new_user_id, 50, "Registration Welcome Bonus"))
            conn.commit()
            conn.close()
            
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            flash(f"Error during registration: {str(e)}", "danger")
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect(url_for('login'))

# 2. Main Shop & Product Views
@app.route('/')
@app.route('/shop')
def shop():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    category_filter = request.args.get('category', '').strip()
    search_query = request.args.get('search', '').strip()
    
    query = "SELECT * FROM products WHERE stock > 0"
    params = []
    
    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)
    if search_query:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        
    cursor.execute(query, params)
    products = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = [row['category'] for row in cursor.fetchall() if row['category']]
    
    conn.close()
    return render_template('shop.html', products=products, categories=categories, selected_category=category_filter, search_query=search_query)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT p.*, u.name as shop_owner_name FROM products p JOIN users u ON p.owner_id = u.id WHERE p.id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        conn.close()
        flash("Product not found.", "danger")
        return redirect(url_for('shop'))
        
    # Handle incoming referral code
    ref_code = request.args.get('ref', '').strip()
    referred_by = None
    
    if ref_code:
        cursor.execute('''
        SELECT u.id, u.name 
        FROM referrals r 
        JOIN users u ON r.referrer_id = u.id 
        WHERE r.code = ? AND r.product_id = ?
        ''', (ref_code, product_id))
        referrer = cursor.fetchone()
        if referrer:
            if 'user_id' in session and referrer['id'] == session['user_id']:
                # Cannot refer self, ignore
                pass
            else:
                session['referral_code'] = ref_code
                session['referral_product_id'] = product_id
                referred_by = referrer['name']
                
    conn.close()
    return render_template('product_detail.html', product=product, referred_by=referred_by)

# 3. Dynamic Dashboards
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = get_current_user()
    role = user['role']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if role == 'Customer':
        # Get Customer order history
        cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user['id'],))
        orders = cursor.fetchall()
        
        # Get Customer referral codes
        cursor.execute('''
        SELECT r.code, p.name as product_name, p.id as product_id
        FROM referrals r
        JOIN products p ON r.product_id = p.id
        WHERE r.referrer_id = ?
        ''', (user['id'],))
        referrals = cursor.fetchall()
        
        # Get referral purchases count & earnings
        cursor.execute('''
        SELECT COUNT(*), SUM(oi.quantity * 5)
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE oi.referral_user_id = ?
        ''', (user['id'],))
        ref_stats = cursor.fetchone()
        ref_purchases_count = ref_stats[0] if ref_stats[0] else 0
        ref_points_earned = ref_stats[1] if ref_stats[1] else 0
        
        conn.close()
        return render_template('dashboard.html', role=role, orders=orders, referrals=referrals, 
                               ref_purchases_count=ref_purchases_count, ref_points_earned=ref_points_earned)
                               
    elif role == 'ShopOwner':
        # Get overall inventory count
        cursor.execute("SELECT COUNT(*), SUM(stock) FROM products WHERE owner_id = ?", (user['id'],))
        inv_row = cursor.fetchone()
        total_products = inv_row[0] if inv_row[0] else 0
        total_stock = inv_row[1] if inv_row[1] else 0
        
        # Calculate business earnings based on standard COGS
        # Gross revenue = sum(purchase_price * qty)
        # Total cost = sum(cost_price * qty)
        # Gross Profit = Revenue - Cost
        cursor.execute('''
        SELECT 
            SUM(oi.purchase_price * oi.quantity) as gross_revenue,
            SUM(p.cost_price * oi.quantity) as total_cogs
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN orders o ON oi.order_id = o.id
        WHERE p.owner_id = ?
        ''', (user['id'],))
        rev_row = cursor.fetchone()
        
        gross_revenue = rev_row['gross_revenue'] if rev_row['gross_revenue'] else 0.0
        total_cogs = rev_row['total_cogs'] if rev_row['total_cogs'] else 0.0
        
        # Referral commission paid out as standard expense (5 points = 0.5 Rs per referral purchase item)
        cursor.execute('''
        SELECT COUNT(*)
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE p.owner_id = ? AND oi.referral_user_id IS NOT NULL
        ''', (user['id'],))
        referred_sales = cursor.fetchone()[0]
        referral_expenses = referred_sales * 0.5 # 5 points = 0.5 Rs
        
        net_profit = gross_revenue - total_cogs - referral_expenses
        
        # Recent sales
        cursor.execute('''
        SELECT oi.*, p.name as product_name, o.created_at, o.status, u.name as buyer_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN orders o ON oi.order_id = o.id
        JOIN users u ON o.user_id = u.id
        WHERE p.owner_id = ?
        ORDER BY o.id DESC LIMIT 5
        ''', (user['id'],))
        recent_sales = cursor.fetchall()
        
        conn.close()
        return render_template('dashboard.html', role=role, total_products=total_products, total_stock=total_stock,
                               gross_revenue=round(gross_revenue, 2), total_cogs=round(total_cogs, 2),
                               referral_expenses=round(referral_expenses, 2), net_profit=round(net_profit, 2),
                               recent_sales=recent_sales)
                               
    elif role == 'Sysadmin':
        # Main Admin Metrics
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*), SUM(final_amount_paid) FROM orders")
        orders_row = cursor.fetchone()
        total_orders = orders_row[0] if orders_row[0] else 0
        total_sales_value = orders_row[1] if orders_row[1] else 0.0
        
        # Recent platform orders
        cursor.execute('''
        SELECT o.*, u.name as buyer_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.id DESC LIMIT 8
        ''')
        recent_orders = cursor.fetchall()
        
        # All users
        cursor.execute("SELECT id, name, email, role, phone FROM users ORDER BY role, id DESC")
        users = cursor.fetchall()
        
        conn.close()
        return render_template('dashboard.html', role=role, total_users=total_users, total_products=total_products,
                               total_orders=total_orders, total_sales_value=round(total_sales_value, 2),
                               recent_orders=recent_orders, users=users)

# 4. JSON API for Shop Owner Analytics (Plotly)
@app.route('/api/owner/analytics-data')
def owner_analytics_data():
    if 'user_id' not in session or session.get('user_role') != 'ShopOwner':
        return jsonify({"error": "Unauthorized"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Product Sales Performance (Quantity Sold & Net Profit)
    cursor.execute('''
    SELECT 
        p.name as product_name,
        SUM(oi.quantity) as total_qty,
        SUM(oi.purchase_price * oi.quantity) as revenue,
        SUM((oi.purchase_price - p.cost_price) * oi.quantity) as gross_profit
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    WHERE p.owner_id = ?
    GROUP BY p.id
    ORDER BY total_qty DESC
    ''', (session['user_id'],))
    sales_perf = cursor.fetchall()
    
    product_names = [row['product_name'] for row in sales_perf]
    quantities = [row['total_qty'] for row in sales_perf]
    revenues = [row['revenue'] for row in sales_perf]
    profits = [row['gross_profit'] for row in sales_perf]
    
    # 2. Sales by Category
    cursor.execute('''
    SELECT 
        p.category,
        SUM(oi.purchase_price * oi.quantity) as revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    WHERE p.owner_id = ?
    GROUP BY p.category
    ''', (session['user_id'],))
    cat_perf = cursor.fetchall()
    categories = [row['category'] if row['category'] else 'General' for row in cat_perf]
    cat_revenues = [row['revenue'] for row in cat_perf]
    
    # 3. Monthly Spend vs. Revenue (Timeline)
    cursor.execute('''
    SELECT 
        strftime('%Y-%m-%d', o.created_at) as order_date,
        SUM(oi.purchase_price * oi.quantity) as day_revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    JOIN orders o ON oi.order_id = o.id
    WHERE p.owner_id = ?
    GROUP BY order_date
    ORDER BY order_date ASC
    ''', (session['user_id'],))
    time_perf = cursor.fetchall()
    dates = [row['order_date'] for row in time_perf]
    date_revenues = [row['day_revenue'] for row in time_perf]
    
    conn.close()
    
    return jsonify({
        "products": {
            "names": product_names,
            "quantities": quantities,
            "revenues": revenues,
            "profits": profits
        },
        "categories": {
            "names": categories,
            "revenues": cat_revenues
        },
        "timeline": {
            "dates": dates,
            "revenues": date_revenues
        }
    })

# 5. Sysadmin Analytics Endpoint
@app.route('/api/admin/analytics-data')
def admin_analytics_data():
    if 'user_id' not in session or session.get('user_role') != 'Sysadmin':
        return jsonify({"error": "Unauthorized"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total revenue per Shop Owner
    cursor.execute('''
    SELECT 
        u.name as owner_name,
        SUM(oi.purchase_price * oi.quantity) as total_sales
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    JOIN users u ON p.owner_id = u.id
    GROUP BY u.id
    ''', [])
    owner_sales = cursor.fetchall()
    owners = [row['owner_name'] for row in owner_sales]
    sales = [row['total_sales'] for row in owner_sales]
    
    # 2. Overall Platform order trends (last 7 days)
    cursor.execute('''
    SELECT 
        strftime('%Y-%m-%d', o.created_at) as order_date,
        COUNT(*) as order_count,
        SUM(o.final_amount_paid) as total_revenue
    FROM orders o
    GROUP BY order_date
    ORDER BY order_date ASC
    LIMIT 7
    ''', [])
    daily_sales = cursor.fetchall()
    dates = [row['order_date'] for row in daily_sales]
    orders_counts = [row['order_count'] for row in daily_sales]
    revenue_sums = [row['total_revenue'] for row in daily_sales]
    
    conn.close()
    return jsonify({
        "owners": {
            "names": owners,
            "sales": sales
        },
        "daily": {
            "dates": dates,
            "counts": orders_counts,
            "revenues": revenue_sums
        }
    })

# 6. Referral Code Generation API
@app.route('/api/generate_referral/<int:product_id>', methods=['POST'])
def generate_referral(product_id):
    if 'user_id' not in session:
        return jsonify({"error": "Please log in first"}), 401
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if referral code already exists for this product and user
    cursor.execute("SELECT code FROM referrals WHERE product_id = ? AND referrer_id = ?", (product_id, user_id))
    existing = cursor.fetchone()
    
    if existing:
        code = existing['code']
    else:
        # Create a unique 8-character code slug
        code = uuid.uuid4().hex[:8].upper()
        cursor.execute("INSERT INTO referrals (product_id, referrer_id, code) VALUES (?, ?, ?)", (product_id, user_id, code))
        conn.commit()
        
    conn.close()
    
    # Construct absolute link matching local environment dynamically
    ref_url = url_for('product_detail', product_id=product_id, ref=code, _external=True)
    return jsonify({"success": True, "code": code, "ref_url": ref_url})

# 7. Cart Operations
@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    cart_items = []
    subtotal = 0.0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for pid, qty in list(cart.items()):
        cursor.execute("SELECT * FROM products WHERE id = ?", (int(pid),))
        product = cursor.fetchone()
        if product and product['stock'] > 0:
            qty = min(qty, product['stock']) # Clamp to available stock
            total_item_price = product['sale_price'] * qty
            subtotal += total_item_price
            cart_items.append({
                'id': product['id'],
                'name': product['name'],
                'sale_price': product['sale_price'],
                'stock': product['stock'],
                'image_url': product['image_url'],
                'quantity': qty,
                'total_price': total_item_price
            })
        else:
            cart.pop(pid, None) # Remove out-of-stock items
            session.modified = True
            
    conn.close()
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal)

@app.route('/api/cart/add', methods=['POST'])
def cart_add():
    data = request.get_json()
    product_id = str(data.get('product_id'))
    quantity = int(data.get('quantity', 1))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if not product:
        return jsonify({"success": False, "message": "Product not found."})
        
    cart = session.get('cart', {})
    current_qty = cart.get(product_id, 0)
    new_qty = current_qty + quantity
    
    if new_qty > product['stock']:
        return jsonify({"success": False, "message": f"Only {product['stock']} units available in stock."})
        
    cart[product_id] = new_qty
    session['cart'] = cart
    session.modified = True
    
    return jsonify({"success": True, "message": "Product added to cart!", "cart_count": sum(cart.values())})

@app.route('/api/cart/update', methods=['POST'])
def cart_update():
    data = request.get_json()
    product_id = str(data.get('product_id'))
    quantity = int(data.get('quantity', 1))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if not product:
        return jsonify({"success": False, "message": "Product not found."})
        
    if quantity > product['stock']:
        return jsonify({"success": False, "message": f"Only {product['stock']} units available in stock."})
        
    cart = session.get('cart', {})
    if quantity <= 0:
        cart.pop(product_id, None)
    else:
        cart[product_id] = quantity
        
    session['cart'] = cart
    session.modified = True
    
    return jsonify({"success": True, "message": "Cart updated!"})

@app.route('/api/cart/remove', methods=['POST'])
def cart_remove():
    data = request.get_json()
    product_id = str(data.get('product_id'))
    
    cart = session.get('cart', {})
    cart.pop(product_id, None)
    session['cart'] = cart
    session.modified = True
    
    return jsonify({"success": True, "message": "Item removed from cart!"})

# 8. Checkout & Payment Gateway
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash("Please log in to proceed to checkout.", "warning")
        return redirect(url_for('login'))
        
    cart = session.get('cart', {})
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for('shop'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate cart total and details
    cart_items = []
    subtotal = 0.0
    for pid, qty in list(cart.items()):
        cursor.execute("SELECT * FROM products WHERE id = ?", (int(pid),))
        product = cursor.fetchone()
        if product and product['stock'] >= qty:
            total_item_price = product['sale_price'] * qty
            subtotal += total_item_price
            cart_items.append({
                'id': product['id'],
                'name': product['name'],
                'sale_price': product['sale_price'],
                'stock': product['stock'],
                'quantity': qty,
                'total_price': total_item_price
            })
        else:
            conn.close()
            flash("Some items in your cart became unavailable. Please verify your cart.", "danger")
            return redirect(url_for('view_cart'))
            
    user_points = get_user_points(session['user_id'])
    max_discount_rs = round(user_points * 0.1, 2)
    
    if request.method == 'POST':
        address = request.form['address'].strip()
        points_to_use = int(request.form.get('points_to_use', 0))
        
        if not address:
            conn.close()
            flash("Shipping address is required.", "danger")
            return redirect(url_for('checkout'))
            
        if points_to_use > user_points:
            points_to_use = user_points
            
        discount_rs = round(points_to_use * 0.1, 2)
        if discount_rs > subtotal:
            discount_rs = subtotal
            points_to_use = int(discount_rs * 10)
            
        final_pay = round(subtotal - discount_rs, 2)
        
        # 1. Deduct products stock
        for item in cart_items:
            cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item['quantity'], item['id']))
            
        # 2. Insert Order
        # Every purchase awards 10 points!
        points_earned = 10
        cursor.execute('''
        INSERT INTO orders (user_id, shipping_address, total_original_price, points_applied_discount, final_amount_paid, points_earned, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending')
        ''', (session['user_id'], address, subtotal, discount_rs, final_pay, points_earned))
        order_id = cursor.lastrowid
        
        # 3. Deduct points if user spent them
        if points_to_use > 0:
            cursor.execute('''
            INSERT INTO wallet_transactions (user_id, points_change, description)
            VALUES (?, ?, ?)
            ''', (session['user_id'], -points_to_use, f"Points applied as ₹{discount_rs} discount for Order #{order_id}"))
            
        # 4. Credit points for purchase
        cursor.execute('''
        INSERT INTO wallet_transactions (user_id, points_change, description)
        VALUES (?, ?, ?)
        ''', (session['user_id'], points_earned, f"Points earned from Direct Purchase (Order #{order_id})"))
        
        # 5. Insert order items & check immediate referrals!
        referral_code = session.get('referral_code')
        referral_pid = session.get('referral_product_id')
        
        for item in cart_items:
            ref_user_id = None
            
            # Check if this item matches immediate referral criteria
            if referral_code and referral_pid == item['id']:
                # Lookup referrer
                cursor.execute("SELECT referrer_id FROM referrals WHERE code = ? AND product_id = ?", (referral_code, item['id']))
                ref_row = cursor.fetchone()
                if ref_row and ref_row['referrer_id'] != session['user_id']:
                    ref_user_id = ref_row['referrer_id']
                    
                    # Award 5 points to referrer!
                    cursor.execute('''
                    INSERT INTO wallet_transactions (user_id, points_change, description)
                    VALUES (?, ?, ?)
                    ''', (ref_user_id, 5, f"Referral purchase bonus (Customer bought product ID {item['id']})"))
                    
            cursor.execute('''
            INSERT INTO order_items (order_id, product_id, quantity, purchase_price, referral_user_id)
            VALUES (?, ?, ?, ?, ?)
            ''', (order_id, item['id'], item['quantity'], item['sale_price'], ref_user_id))
            
        conn.commit()
        conn.close()
        
        # Clear cart and referral session after immediate check-out
        session.pop('cart', None)
        session.pop('referral_code', None)
        session.pop('referral_product_id', None)
        
        flash(f"Order #{order_id} placed successfully! You earned {points_earned} points.", "success")
        return redirect(url_for('dashboard'))
        
    conn.close()
    return render_template('checkout.html', cart_items=cart_items, subtotal=subtotal, user_points=user_points, max_discount_rs=max_discount_rs)

# 9. User Profile & Bank Withdrawals
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = get_current_user()
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        bank_acc = request.form.get('bank_account', '').strip()
        bank_ifsc = request.form.get('bank_ifsc', '').strip()
        
        if not name or not email or not phone:
            flash("Required fields cannot be empty.", "danger")
            return redirect(url_for('profile'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email is already taken by someone else
        cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user['id']))
        if cursor.fetchone():
            conn.close()
            flash("Email is already in use by another user.", "danger")
            return redirect(url_for('profile'))
            
        cursor.execute('''
        UPDATE users 
        SET name = ?, email = ?, phone = ?, bank_account_number = ?, bank_ifsc = ?
        WHERE id = ?
        ''', (name, email, phone, bank_acc, bank_ifsc, user['id']))
        conn.commit()
        conn.close()
        
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))
        
    # Get user wallet history for audit trail
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wallet_transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user['id'],))
    transactions = cursor.fetchall()
    conn.close()
    
    return render_template('profile.html', user=user, transactions=transactions)

@app.route('/profile/withdraw', methods=['POST'])
def withdraw_points():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    points_to_withdraw = int(request.form.get('points', 0))
    user = get_current_user()
    current_pts = get_user_points(user['id'])
    
    if not user['bank_account_number'] or not user['bank_ifsc']:
        flash("Please update your Bank Account Number and IFSC Code in your profile before withdrawing.", "danger")
        return redirect(url_for('profile'))
        
    if points_to_withdraw <= 0:
        flash("Please enter a valid amount of points to withdraw.", "danger")
        return redirect(url_for('profile'))
        
    if points_to_withdraw > current_pts:
        flash("Insufficient points balance.", "danger")
        return redirect(url_for('profile'))
        
    cash_withdrawn = round(points_to_withdraw * 0.1, 2)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # Record withdrawal transaction
    cursor.execute('''
    INSERT INTO wallet_transactions (user_id, points_change, description)
    VALUES (?, ?, ?)
    ''', (user['id'], -points_to_withdraw, f"Withdrew ₹{cash_withdrawn} to Bank A/C ({user['bank_account_number'][-4:]})"))
    conn.commit()
    conn.close()
    
    flash(f"Withdrawal of ₹{cash_withdrawn} initiated successfully! It will reflect in your bank account shortly.", "success")
    return redirect(url_for('profile'))

# 10. Shop Owner Inventory Management
@app.route('/owner/products', methods=['GET', 'POST'])
def owner_products():
    if 'user_id' not in session or session.get('user_role') != 'ShopOwner':
        flash("Access restricted to Shop Owners.", "danger")
        return redirect(url_for('shop'))
        
    user = get_current_user()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form['name'].strip()
        description = request.form['description'].strip()
        category = request.form['category'].strip()
        cost_price = float(request.form['cost_price'])
        sale_price = float(request.form['sale_price'])
        stock = int(request.form['stock'])
        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            filename = uuid.uuid4().hex + '_' + image_file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            image_url = '/static/uploads/' + filename
        else:
            image_url = request.form.get('image_url', '').strip()
        
        if not image_url:
            image_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500" # fallback
            
        if action == 'add':
            cursor.execute('''
            INSERT INTO products (owner_id, name, description, category, cost_price, sale_price, stock, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user['id'], name, description, category, cost_price, sale_price, stock, image_url))
            conn.commit()
            flash(f"Product '{name}' added successfully!", "success")
            
        elif action == 'edit':
            product_id = int(request.form['product_id'])
            cursor.execute('''
            UPDATE products 
            SET name = ?, description = ?, category = ?, cost_price = ?, sale_price = ?, stock = ?, image_url = ?
            WHERE id = ? AND owner_id = ?
            ''', (name, description, category, cost_price, sale_price, stock, image_url, product_id, user['id']))
            conn.commit()
            flash(f"Product '{name}' updated successfully!", "success")
            
    # Get all products owned by this seller
    cursor.execute("SELECT * FROM products WHERE owner_id = ? ORDER BY id DESC", (user['id'],))
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('owner_products.html', products=products)

@app.route('/owner/products/delete/<int:product_id>', methods=['POST'])
def owner_delete_product(product_id):
    if 'user_id' not in session or session.get('user_role') != 'ShopOwner':
        return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ? AND owner_id = ?", (product_id, session['user_id']))
    conn.commit()
    conn.close()
    flash("Product deleted successfully.", "success")
    return redirect(url_for('owner_products'))

# 11. Sysadmin Management
@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if 'user_id' not in session or session.get('user_role') != 'Sysadmin':
        flash("Access restricted to Admins.", "danger")
        return redirect(url_for('shop'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form['name'].strip()
        description = request.form['description'].strip()
        category = request.form['category'].strip()
        cost_price = float(request.form['cost_price'])
        sale_price = float(request.form['sale_price'])
        stock = int(request.form['stock'])
        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            filename = uuid.uuid4().hex + '_' + image_file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            image_url = '/static/uploads/' + filename
        else:
            image_url = request.form.get('image_url', '').strip()
        product_id = int(request.form['product_id'])
        
        if action == 'edit':
            cursor.execute('''
            UPDATE products 
            SET name = ?, description = ?, category = ?, cost_price = ?, sale_price = ?, stock = ?, image_url = ?
            WHERE id = ?
            ''', (name, description, category, cost_price, sale_price, stock, image_url, product_id))
            conn.commit()
            flash("Product updated successfully by Admin.", "success")
            
    cursor.execute("SELECT p.*, u.name as shop_owner_name FROM products p JOIN users u ON p.owner_id = u.id ORDER BY p.id DESC")
    products = [dict(row) for row in cursor.fetchall()]
    
    # Get list of all order statuses
    cursor.execute("SELECT o.*, u.name as buyer_name FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.id DESC")
    orders = cursor.fetchall()
    
    conn.close()
    return render_template('admin_products.html', products=products, orders=orders)

@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
def admin_delete_product(product_id):
    if 'user_id' not in session or session.get('user_role') != 'Sysadmin':
        return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash("Product removed by Admin.", "success")
    return redirect(url_for('admin_products'))

@app.route('/admin/orders/update-status/<int:order_id>', methods=['POST'])
def admin_update_order_status(order_id):
    if 'user_id' not in session or session.get('user_role') != 'Sysadmin':
        return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    new_status = request.form.get('status')
    if new_status not in ['Pending', 'Shipped', 'Delivered']:
        flash("Invalid status selected.", "danger")
        return redirect(url_for('admin_products'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    
    flash(f"Order #{order_id} status updated to '{new_status}' successfully.", "success")
    return redirect(url_for('admin_products'))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
