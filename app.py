from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort, Response, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from datetime import datetime, timezone
import pymysql
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://portfolio:8MEPBTxaaZRaKxs8@191.252.100.132/portfolio'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Cria a pasta se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  # Novo campo


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='comments', lazy=True)  # Relacionamento com User


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))
    scheduled_for = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    main_image = db.Column(db.String(255))  # <-- Adiciona esse campo aqui
    comments = db.relationship('Comment', backref='post', lazy=True)
    user = db.relationship('User', backref='posts')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def get_link(self):
        return f"https://chiapettadev.site/posts/{self.slug}"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

class AnonymousUser(AnonymousUserMixin):
    role = 'user'  # Ou None/outro valor padrão

def get_recent_posts():
    fuso_sp = pytz.timezone('America/Sao_Paulo')
    current_time = datetime.now(fuso_sp)
    
    posts = Post.query.filter(
        db.or_(
            Post.is_published == True,
            db.and_(
                Post.scheduled_for.isnot(None),
                Post.scheduled_for <= current_time
            )
        )
    ).order_by(Post.created_at.desc()).limit(3).all()
    
    return [{
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'created_at': post.created_at.astimezone(fuso_sp).strftime('%d/%m/%Y %H:%M')
    } for post in posts]


    
    
def publish_scheduled_posts():
    with app.app_context():
        fuso_sp = pytz.timezone('America/Sao_Paulo')
        current_time = datetime.now(fuso_sp)
        
        scheduled_posts = Post.query.filter(
            Post.is_published == False,
            Post.scheduled_for <= current_time
        ).all()

        for post in scheduled_posts:
            post.is_published = True
        
        db.session.commit()


@app.route('/')
def home():
    skills = [
        "Python", "Flask", "HTML", "CSS", "JavaScript",
        "SQL", "Git", "Linux", "Desenvolvimento Web", "Manutenção de Computadores"
    ]
    recent_posts = get_recent_posts()
    return render_template('index.html', skills=skills, recent_posts=recent_posts, current_user=current_user)

@app.route('/post/<int:post_id>')
def post(post_id):
    post = Post.query.get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post.id).order_by(Comment.created_at.desc()).all()
    
    post_dict = {
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'created_at': post.created_at.strftime('%d/%m/%Y %H:%M'),
        'scheduled_for': post.scheduled_for.strftime('%d/%m/%Y %H:%M'),
        'user': post.user.username
    }

    recent_posts = get_recent_posts()
    
    return render_template('post.html', post=post_dict, recent_posts=recent_posts, comments=comments, user=current_user)


@app.route('/create', methods=['GET', 'POST'])
@admin_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        scheduled_date = request.form.get('scheduled_date')
        scheduled_time = request.form.get('scheduled_time')
        
        fuso_sp = pytz.timezone('America/Sao_Paulo')

        if not title or not content:
            flash('Título e conteúdo são obrigatórios!', 'danger')
            return redirect(url_for('create'))
        
        image_file = request.files.get('main_image')
        main_image_filename = None

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            main_image_filename = filename


        new_post = Post(
            title=title,
            content=content,
            main_image=main_image_filename,
            is_published=False,
            user_id=current_user.id
        )

        if scheduled_date and scheduled_time:
            try:
                scheduled_datetime = datetime.strptime(
                    f"{scheduled_date} {scheduled_time}",
                    "%Y-%m-%d %H:%M"
                )
                # Localiza o horário em São Paulo
                scheduled_datetime = fuso_sp.localize(scheduled_datetime)
                new_post.scheduled_for = scheduled_datetime
            except ValueError:
                flash('Data ou hora inválida!', 'danger')
                return redirect(url_for('create'))

        db.session.add(new_post)
        db.session.commit()
        flash('Post agendado com sucesso!', 'success')
        return redirect(url_for('all_posts'))

    return render_template('create.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, role='user')
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registro bem-sucedido! Faça login.', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Usuário já existe.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)  # Autentica o usuário antes de verificar a role
            
            # Verificação de role após login
            if user.role == 'admin':  # Corrigido: usar user.role em vez de current_user
                flash('Login admin realizado com sucesso!', 'success')
                return redirect(url_for('all_posts'))
            else:
                flash('Login de usuário realizado!', 'success')
                return redirect(url_for('home'))
        else:
            flash('Combinação usuário/senha incorreta', 'danger')
    
    return render_template('login.html')


@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('content')
    
    if not content:
        flash('O comentário não pode estar vazio.', 'danger')
        return redirect(url_for('post', post_id=post_id))
    
    comment = Comment(post_id=post_id, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()
    
    flash('Comentário adicionado com sucesso!', 'success')
    return redirect(url_for('post', post_id=post_id))

@app.route('/posts')
@admin_required
def all_posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('all_posts.html', posts=posts)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post:
        db.session.delete(post)
        db.session.commit()
        flash('Post excluído com sucesso!', 'success')
    return redirect(url_for('all_posts'))

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    fuso_sp = pytz.timezone('America/Sao_Paulo')
    image_file = request.files.get('main_image')
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(image_path)
        post.main_image = filename


    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        scheduled_date = request.form.get('scheduled_date')
        scheduled_time = request.form.get('scheduled_time')

        if not title or not content:
            flash('Título e conteúdo são obrigatórios!', 'danger')
            return redirect(url_for('edit_post', post_id=post.id))

        post.title = title
        post.content = content
        
        if scheduled_date and scheduled_time:
            try:
                scheduled_datetime = datetime.strptime(
                    f"{scheduled_date} {scheduled_time}",
                    "%Y-%m-%d %H:%M"
                )
                # Localiza o horário em São Paulo
                scheduled_datetime = fuso_sp.localize(scheduled_datetime)
                post.scheduled_for = scheduled_datetime
                post.is_published = False
            except ValueError:
                flash('Data ou hora inválida!', 'danger')
                return redirect(url_for('edit_post', post_id=post.id))
        else:
            post.scheduled_for = None
            post.is_published = True

        db.session.commit()
        flash('Post atualizado com sucesso!', 'success')
        return redirect(url_for('all_posts'))

    return render_template('edit_post.html', post=post)

@app.route("/feed")
def rss_feed():
    posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()
    
    rss_template = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Chiapetta Dev Blog</title>
        <link>https://chiapettadev.site</link>
        <description>Últimos posts do Chiapetta Dev</description>
        {% for post in posts %}
        <item>
          <title>{{ post.title }}</title>
          <image>{{ post.main_image }}</image>
          <description><![CDATA[{{ post.content[:150] }}...]]></description>
          <pubDate>{{ post.created_at.strftime('%a, %d %b %Y %H:%M:%S +0000') }}</pubDate>
        </item>
        {% endfor %}
      </channel>
    </rss>
    """

    rss_xml = render_template_string(rss_template, posts=posts)
    return Response(rss_xml, mimetype='application/rss+xml')



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=7000)
