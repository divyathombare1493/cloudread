import os
from flask import Flask, render_template, redirect, url_for, flash, session, request, jsonify
import bcrypt
from flask_mysqldb import MySQL
from datetime import datetime
from validate_login_form import LoginForm
from validate_register_form import RegisterForm
from validate_add_book_form import AddBookForm
from gcs import upload_file

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '__FILL_IN__')

app.config['MYSQL_UNIX_SOCKET'] = f"/cloudsql/{os.environ['CLOUD_SQL_CONNECTION_NAME']}"
app.config['MYSQL_USER']     = os.environ['MYSQL_USER']
app.config['MYSQL_PASSWORD'] = os.environ['MYSQL_PASSWORD']
app.config['MYSQL_DB']       = os.environ['MYSQL_DB']

# app.config['SECRET_KEY'] = 'your_secret_key'
# app.config['MYSQL_HOST'] = '127.0.0.1'
# app.config['MYSQL_USER'] = 'root'
# app.config['MYSQL_PASSWORD'] = 'Kunal@123'
# app.config['MYSQL_DB'] = 'mydatabase'

mysql = MySQL(app)



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        first_name = form.first_name.data
        last_name = form.last_name.data
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT 1 FROM user_info WHERE email=%s", (email,))
        existing = cursor.fetchone()
        cursor.close()
        if existing:
            form.email.errors.append('An account with this email already exists.')
            return render_template('register.html', form=form)

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        userRolId = 1
        isActive = 1
        createdAt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO user_info (first_name, last_name, email, password, userRolId, isActive, createdAt) VALUES (%s, %s, %s, %s, %s, %s, %s)', (first_name, last_name, email, hashed_password, userRolId, isActive, createdAt))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM user_info WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[4]):
            session['user_id'] = user[0]
            session['user_role_id'] = user[5]
            session['user_first_name'] = user[1]
            session['user_last_name'] = user[2]
            return redirect(url_for('dashboard'))
        else:
            flash("Login failed. Please check your email and password")
            return redirect(url_for('login'))
    return render_template('login.html',form=form)

@app.route('/dashboard', methods=['GET'])
def dashboard():
    cursor = mysql.connection.cursor()
    user_role_id = session.get('user_role_id', '')
    if user_role_id == 1:
        cursor.execute("""
            SELECT e.ebookId,
                   e.ebookName,
                   e.ebookLink,
                   e.ebookCoverPageLink,
                   ucb.isReading,
                   ucb.isCompleted,
                   ec.ebookCategoryName,
                   ec.ebookCategoryId,
                   ucb.createdDate,
                   ucb.modifiedDate
            FROM user_current_book ucb
            INNER JOIN ebooks e ON ucb.ebookId = e.ebookId
            INNER JOIN ebook_category ec ON e.ebookCategoryId = ec.ebookCategoryId
            WHERE ucb.userId = %s
              AND e.isActive = 1
              AND ec.isActive = 1
            ORDER BY ucb.modifiedDate DESC
        """, (session['user_id'],))
    else:
        cursor.execute("""
            SELECT e.ebookCategoryId, e.ebookName, e.ebookLink,
                e.ebookCoverPageLink, e.isActive, e.createdDate,
                c.ebookCategoryName, e.ebookId
            FROM ebooks e
            LEFT JOIN ebook_category c
                ON c.ebookCategoryId = e.ebookCategoryId
            WHERE e.isActive = 1
        """)
    ebooks = cursor.fetchall()
    cursor.close()
    first_name = session.get('user_first_name', '')
    last_name = session.get('user_last_name', '')
    return render_template('dashboard.html', ebooks=ebooks,
                           first_name=first_name, last_name=last_name,
                           user_role_id=user_role_id)

@app.route('/api/search-books', methods=['GET'])
def search_books():
    name = request.args.get('name', '').strip()
    user_role_id = session.get('user_role_id', '')
    cursor = mysql.connection.cursor()
    if user_role_id == 1:
        cursor.execute("""
            SELECT e.ebookCategoryId, e.ebookName, e.ebookLink,
                   e.ebookCoverPageLink, e.isActive, e.createdDate,
                   c.ebookCategoryName
            FROM ebooks e
            LEFT JOIN ebook_category c
                ON c.ebookCategoryId = e.ebookCategoryId
            INNER JOIN user_current_book ucb ON ucb.ebookId = e.ebookId
            WHERE e.isActive = 1
              AND ucb.userId = %s
              AND e.ebookName LIKE %s
        """, (session['user_id'], '%' + name + '%'))
    else:
        cursor.execute("""
            SELECT e.ebookCategoryId, e.ebookName, e.ebookLink,
                   e.ebookCoverPageLink, e.isActive, e.createdDate,
                   c.ebookCategoryName, e.ebookId
            FROM ebooks e
            LEFT JOIN ebook_category c
                ON c.ebookCategoryId = e.ebookCategoryId
            WHERE e.isActive = 1 AND e.ebookName LIKE %s
        """, ('%' + name + '%',))
    rows = cursor.fetchall()
    cursor.close()
    books = []
    for r in rows:
        books.append({
            'ebookName': r[1],
            'ebookLink': r[2],
            'ebookCoverPageLink': r[3],
            'ebookCategoryName': r[6],
            'ebookId': r[7] if user_role_id == 0 and len(r) > 7 else None,
        })
    return jsonify(books)

@app.route('/api/search-by-genre', methods=['GET'])
def search_by_genre():
    genre = request.args.get('genre', '').strip()
    user_role_id = session.get('user_role_id', '')
    cursor = mysql.connection.cursor()
    if user_role_id == 1:
        cursor.execute("""
            SELECT e.ebookCategoryId, e.ebookName, e.ebookLink,
                   e.ebookCoverPageLink, e.isActive, e.createdDate,
                   c.ebookCategoryName
            FROM ebooks e
            INNER JOIN ebook_category c
                ON c.ebookCategoryId = e.ebookCategoryId
            INNER JOIN user_current_book ucb ON ucb.ebookId = e.ebookId
            WHERE e.isActive = 1
              AND ucb.userId = %s
              AND c.ebookCategoryName LIKE %s
        """, (session['user_id'], '%' + genre + '%'))
    else:
        cursor.execute("""
            SELECT e.ebookCategoryId, e.ebookName, e.ebookLink,
                   e.ebookCoverPageLink, e.isActive, e.createdDate,
                   c.ebookCategoryName, e.ebookId
            FROM ebooks e
            INNER JOIN ebook_category c
                ON c.ebookCategoryId = e.ebookCategoryId
            WHERE e.isActive = 1
              AND c.ebookCategoryName LIKE %s
        """, ('%' + genre + '%',))
    rows = cursor.fetchall()
    cursor.close()
    books = []
    for r in rows:
        books.append({
            'ebookName': r[1],
            'ebookLink': r[2],
            'ebookCoverPageLink': r[3],
            'ebookCategoryName': r[6],
            'ebookId': r[7] if user_role_id == 0 and len(r) > 7 else None,
        })
    return jsonify(books)

@app.route('/my-books/add', methods=['GET', 'POST'])
def add_to_my_books():
    if session.get('user_role_id') != 1:
        flash('You are not authorized to access this page.')
        return redirect(url_for('dashboard'))

    user_id = session['user_id']

    if request.method == 'POST':
        ebook_id = request.form.get('ebook_id', type=int)
        # if not ebook_id:
        #     flash('Please select a book to add.')
        #     return redirect(url_for('add_to_my_books'))

        cursor = mysql.connection.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO user_current_book (userId, ebookId, isReading, isCompleted, createdDate, modifiedDate) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, ebook_id, 1, 0, now, now),
        )
        mysql.connection.commit()
        cursor.close()
        flash('Book added to your dashboard.')
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT e.ebookId, e.ebookName, e.ebookLink, e.ebookCoverPageLink,
               c.ebookCategoryName
        FROM ebooks e
        LEFT JOIN ebook_category c ON c.ebookCategoryId = e.ebookCategoryId
        WHERE e.isActive = 1
          AND e.ebookId NOT IN (
              SELECT ebookId FROM user_current_book WHERE userId = %s
          )
        ORDER BY e.ebookName
    """, (user_id,))
    available_books = cursor.fetchall()
    cursor.close()
    return render_template('add_to_my_books.html', books=available_books)


@app.route('/admin/add-book', methods=['GET', 'POST'])
def add_book():
    if session.get('user_role_id') != 0:
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT ebookCategoryId, ebookCategoryName FROM ebook_category WHERE isActive=1 ORDER BY ebookCategoryName")
    categories = cursor.fetchall()
    cursor.close()

    form = AddBookForm()
    choices = []
    for row in categories:
        choices.append((row[0], row[1]))
    form.ebook_category_id.choices = choices

    if form.validate_on_submit():
        pdf_url = upload_file(form.ebook_pdf.data, folder='ebooks')
        cover_url = upload_file(form.ebook_cover.data, folder='covers')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO ebooks (ebookCategoryId, ebookName, ebookLink, ebookCoverPageLink, isActive, createdDate) VALUES (%s, %s, %s, %s, %s, %s)",
            (form.ebook_category_id.data, form.ebook_name.data, pdf_url, cover_url, 1, created_at),
        )
        mysql.connection.commit()
        cursor.close()
        flash('Book added successfully.')
        return redirect(url_for('dashboard'))

    return render_template('add_book.html', form=form)


@app.route('/admin/delete-book', methods=['POST'])
def delete_book():
    if session.get('user_role_id') != 0:
        return redirect(url_for('dashboard'))
    ebook_id = request.form.get('ebook_id', type=int)
    if not ebook_id:
        return redirect(url_for('dashboard'))
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE ebooks SET isActive = 0 WHERE ebookId = %s", (ebook_id,))
    mysql.connection.commit()
    cursor.close()
    flash('Book removed from catalog.')
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))




if __name__ == '__main__':
    app.run(debug=True)
