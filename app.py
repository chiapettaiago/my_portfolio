from functools import wraps
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, abort, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pytz
from datetime import datetime
import os
import pymysql
import memcache
import logging

# Configurando logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configurações iniciais
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta'

# Configuração do MySQL usando variáveis de ambiente
mysql_host = os.getenv('MYSQL_HOST', '191.252.100.132')
mysql_port = os.getenv('MYSQL_PORT', '3306')
mysql_user = 'portfolio'
mysql_password = '8MEPBTxaaZRaKxs8'
mysql_db = 'portfolio'

# Log das configurações de conexão
logger.debug(f"Tentando conectar ao MySQL em: {mysql_host}:{mysql_port}")
logger.debug(f"Usuário: {mysql_user}")
logger.debug(f"Database: {mysql_db}")

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_db}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Otimizações de memória para SQLAlchemy com configurações específicas do MySQL
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 10,
    'echo': True,  # Ativando logs SQL para debug
    'connect_args': {
        'connect_timeout': 30,  # Aumentando o timeout para 30 segundos
        'charset': 'utf8mb4',
        'use_unicode': True,
        'client_flag': pymysql.constants.CLIENT.MULTI_STATEMENTS
    }
}

# Configuração do Memcached usando variáveis de ambiente
memcached_host = os.getenv('MEMCACHED_HOST', '191.252.100.132')
memcached_port = os.getenv('MEMCACHED_PORT', '11211')
mc = memcache.Client([f'{memcached_host}:{memcached_port}'], debug=1)  # Ativando debug do memcached
CACHE_TIMEOUT = 300  # 5 minutos em segundos

# Pasta de upload e limites
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Extensões
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Teste de conexão inicial
try:
    with app.app_context():
        db.engine.connect()
        logger.info("Conexão com o banco de dados estabelecida com sucesso!")
except Exception as e:
    logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
    raise

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='comments', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')))
    scheduled_for = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    main_image = db.Column(db.String(255))  # agora armazena o nome do arquivo
    comments = db.relationship('Comment', backref='post', lazy=True)
    user = db.relationship('User', backref='posts')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class AnonymousUser(AnonymousUserMixin):
    role = 'user'

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

# Helpers
def get_recent_posts():
    # Tenta buscar do cache primeiro
    cache_key = 'recent_posts'
    cached_posts = mc.get(cache_key)
    
    if cached_posts is not None:
        return cached_posts
        
    # Se não estiver no cache, busca do banco
    fuso_sp = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(fuso_sp)
    
    # Carrega os posts com todos os campos necessários
    posts = Post.query.filter(
        db.or_(
            Post.is_published == True,
            db.and_(Post.scheduled_for.isnot(None), Post.scheduled_for <= now)
        )
    ).order_by(Post.created_at.desc()).limit(3).all()
    
    posts_data = [{
        'id': p.id,
        'title': p.title,
        'content': p.content,
        'main_image': p.main_image,
        'created_at': p.created_at.astimezone(fuso_sp).strftime('%d/%m/%Y %H:%M')
    } for p in posts]
    
    # Salva no cache
    mc.set(cache_key, posts_data, CACHE_TIMEOUT)
    return posts_data

def publish_scheduled_posts():
    with app.app_context():
        fuso_sp = pytz.timezone('America/Sao_Paulo')
        now = datetime.now(fuso_sp)
        pendentes = Post.query.filter(Post.is_published==False, Post.scheduled_for<=now).all()
        for p in pendentes:
            p.is_published = True
        db.session.commit()

# Rotas
@app.route('/')
def home():
    skills = ["Python","Flask","HTML","CSS","JavaScript","SQL","Git","Linux","Desenvolvimento Web"]
    recent_posts = get_recent_posts()
    return render_template('index.html', skills=skills, recent_posts=recent_posts, current_user=current_user)

@app.route('/posts')
@admin_required
def all_posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('all_posts.html', posts=posts)

@app.route('/posts_all')
def posts_all():
    # Lista posts publicados e agendados
    fuso_sp = pytz.timezone('America/Sao_Paulo')
    now = datetime.now(fuso_sp)
    posts = Post.query.filter(
        db.or_(
            Post.is_published == True,
            db.and_(Post.scheduled_for.isnot(None), Post.scheduled_for <= now)
        )
    ).order_by(Post.created_at.desc()).all()
    return render_template('posts_list.html', posts=posts, current_user=current_user)

@app.route('/post/<int:post_id>')
def post_view(post_id):
    # Tenta buscar do cache primeiro
    cache_key = f'post_{post_id}'
    cached_post = mc.get(cache_key)
    cached_comments = mc.get(f'comments_{post_id}')
    
    if cached_post is None:
        # Carrega o post completo
        post = Post.query.get_or_404(post_id)
        
        post_dict = {
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'main_image': post.main_image,
            'created_at': post.created_at.strftime('%d/%m/%Y %H:%M'),
            'scheduled_for': post.scheduled_for.strftime('%d/%m/%Y %H:%M') if post.scheduled_for else '',
            'user': post.user.username if post.user else 'Desconhecido'
        }
        # Salva no cache
        mc.set(cache_key, post_dict, CACHE_TIMEOUT)
    else:
        post_dict = cached_post
    
    if cached_comments is None:
        # Carrega os comentários completos
        comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.desc()).all()
        # Salva no cache
        mc.set(f'comments_{post_id}', comments, CACHE_TIMEOUT)
    else:
        comments = cached_comments
    
    recent_posts = get_recent_posts()
    return render_template('post.html', post=post_dict, recent_posts=recent_posts, comments=comments, current_user=current_user)

@app.route('/create', methods=['GET','POST'])
@admin_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        scheduled_date = request.form.get('scheduled_date')
        scheduled_time = request.form.get('scheduled_time')

        file = request.files.get('main_image')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_post = Post(title=title, content=content, main_image=filename, is_published=False, user_id=current_user.id)

        if scheduled_date and scheduled_time:
            try:
                dt = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
                new_post.scheduled_for = pytz.timezone('America/Sao_Paulo').localize(dt)
            except ValueError:
                flash('Data ou hora inválida!', 'danger')
                return redirect(url_for('create'))

        db.session.add(new_post)
        db.session.commit()
        
        # Invalida o cache de posts recentes
        mc.delete('recent_posts')
        
        flash('Post criado com sucesso! 🚀', 'success')
        return redirect(url_for('all_posts'))

    return render_template('create.html')

@app.route('/post/<int:post_id>/edit', methods=['GET','POST'])
@admin_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']

        file = request.files.get('main_image')
        if file and allowed_file(file.filename):
            fname = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            post.main_image = fname

        sd = request.form.get('scheduled_date')
        st = request.form.get('scheduled_time')
        if sd and st:
            try:
                dt = datetime.strptime(f"{sd} {st}", "%Y-%m-%d %H:%M")
                post.scheduled_for = pytz.timezone('America/Sao_Paulo').localize(dt)
                post.is_published = False
            except ValueError:
                flash('Data ou hora inválida!', 'danger')
                return redirect(url_for('edit_post', post_id=post.id))
        else:
            post.scheduled_for = None
            post.is_published = True

        db.session.commit()
        
        # Invalida os caches relacionados
        mc.delete(f'post_{post_id}')
        mc.delete('recent_posts')
        
        flash('Post atualizado com sucesso! 🎉', 'success')
        return redirect(url_for('all_posts'))

    return render_template('edit_post.html', post=post)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    
    # Invalida os caches relacionados
    mc.delete(f'post_{post_id}')
    mc.delete(f'comments_{post_id}')
    mc.delete('recent_posts')
    
    return redirect(url_for('all_posts'))

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('content')
    if not content:
        flash('Comentário vazio não vale! 😅', 'danger')
        return redirect(url_for('post_view', post_id=post_id))
    comment = Comment(post_id=post_id, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()
    
    # Invalida o cache de comentários
    mc.delete(f'comments_{post_id}')
    
    flash('Comentário adicionado!', 'success')
    return redirect(url_for('post_view', post_id=post_id))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        new_user = User(username=username, password=password, role='user')
        try:
            db.session.add(new_user); db.session.commit()
            flash('Registro ok! Faça login 😉', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Usuário já existe!', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            flash('Bem-vindo de volta!', 'success')
            return redirect(url_for('all_posts' if user.role=='admin' else 'home'))
        flash('Usuário/senha inválidos', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/feed')
def rss_feed():
    # Carrega os posts completos para o feed
    posts = Post.query.order_by(Post.created_at.desc()).limit(10).all()
    
    rss = render_template_string(
        """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
        <title>Chiapetta Dev</title><link>https://chiapettadev.site</link>
        <description>Últimos posts</description>
        {% for p in posts %}
          <item><title>{{p.title}}</title>
          <description><![CDATA[{{p.content[:150]}}...]]></description>
          <pubDate>{{p.created_at.strftime('%a, %d %b %Y %H:%M:%S +0000')}}</pubDate>
          </item>
        {% endfor %}
        </channel></rss>""", posts=posts
    )
    return Response(rss, mimetype='application/rss+xml')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=7000, threaded=True)
