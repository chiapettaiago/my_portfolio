from functools import wraps
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, abort, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pytz
from datetime import datetime, date, timedelta
import os
import pymysql
import memcache
import logging
import json
from collections import Counter
from user_agents import parse
from werkzeug.middleware.proxy_fix import ProxyFix

# Configurando logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configurações iniciais
app = Flask(__name__)
# Adiciona ProxyFix para confiar no cabeçalho X-Forwarded-For do proxy reverso
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
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

# Modelo para contagem de acessos
class PageView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(255), nullable=False)
    ip = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(255), nullable=True)
    browser = db.Column(db.String(50), nullable=True)
    device_type = db.Column(db.String(20), nullable=True)
    referrer = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

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

# Middleware para registrar acessos às páginas
@app.before_request
def track_page_view():
    # Não registrar solicitações de recursos estáticos, favicon ou para a página de análise
    if (request.path.startswith('/static') or 
        request.path == '/favicon.ico' or 
        request.path == '/analytics'):
        return
    
    # Captura informações do acesso
    user_agent_string = request.headers.get('User-Agent', '')
    user_agent = parse(user_agent_string)
    
    page_view = PageView(
        path=request.path,
        ip=request.remote_addr,
        user_agent=user_agent_string[:255],  # Limita o tamanho para evitar erros
        browser=user_agent.browser.family,
        device_type=('Mobile' if user_agent.is_mobile else 
                    'Tablet' if user_agent.is_tablet else 
                    'PC'),
        referrer=request.referrer[:255] if request.referrer else None,
        user_id=current_user.id if current_user.is_authenticated else None
    )
    
    # Salva a visualização no banco de dados
    db.session.add(page_view)
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

@app.route('/linktree')
def linktree():
    # Lista de links para Linktree
    links = [
        {'name': 'Portfólio', 'url': url_for('home', _external=True)},
        {'name': 'Blog', 'url': url_for('posts_all', _external=True)},
        {'name': 'GitHub', 'url': 'https://github.com/chiapettaiago'},
        {'name': 'LinkedIn', 'url': 'https://www.linkedin.com/in/iago-chiapetta-794b59164/'},
        {'name': 'WhatsApp', 'url': 'https://wa.link/fs04yl'},
    ]
    return render_template('linktree.html', links=links)

@app.route('/analytics')
@admin_required
def analytics():
    # Intervalo de tempo padrão: últimos 30 dias
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Parâmetros para filtro de data
    filter_start = request.args.get('start')
    filter_end = request.args.get('end')
    
    try:
        if filter_start:
            start_date = datetime.strptime(filter_start, '%Y-%m-%d')
        if filter_end:
            end_date = datetime.strptime(filter_end, '%Y-%m-%d')
            # Ajusta para o final do dia
            end_date = end_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        # Em caso de erro de formato, usa o padrão
        start_date = end_date - timedelta(days=30)
        flash('Formato de data inválido. Usando os últimos 30 dias como padrão.', 'warning')
    
    # Busca visualizações no período
    views = PageView.query.filter(
        PageView.timestamp.between(start_date, end_date)
    ).all()
    
    # Estatísticas gerais
    total_views = len(views)
    unique_visitors = len(set(view.ip for view in views))
    
    # Visualizações por dia
    views_by_day = Counter()
    for view in views:
        day_str = view.timestamp.strftime('%Y-%m-%d')
        views_by_day[day_str] += 1
    
    # Visualizações por página
    views_by_page = Counter()
    for view in views:
        views_by_page[view.path] += 1
    
    # Visualizações por dispositivo
    views_by_device = Counter()
    for view in views:
        views_by_device[view.device_type] += 1
    
    # Visualizações por navegador
    views_by_browser = Counter()
    for view in views:
        views_by_browser[view.browser] += 1
    
    # Formatar dados para gráficos
    days = sorted(views_by_day.keys())
    views_count = [views_by_day[day] for day in days]
    
    pages = sorted(views_by_page.items(), key=lambda x: x[1], reverse=True)[:10]
    page_labels = [page[0] for page in pages]
    page_counts = [page[1] for page in pages]
    
    device_labels = list(views_by_device.keys())
    device_counts = list(views_by_device.values())
    
    browser_labels = list(views_by_browser.keys())
    browser_counts = list(views_by_browser.values())
    
    return render_template(
        'analytics.html', 
        total_views=total_views,
        unique_visitors=unique_visitors,
        days_json=json.dumps(days),
        views_json=json.dumps(views_count),
        page_labels_json=json.dumps(page_labels),
        page_counts_json=json.dumps(page_counts),
        device_labels_json=json.dumps(device_labels),
        device_counts_json=json.dumps(device_counts),
        browser_labels_json=json.dumps(browser_labels),
        browser_counts_json=json.dumps(browser_counts),
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=7000, threaded=True)
