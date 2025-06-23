from functools import wraps
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, abort, Response, jsonify
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
import uuid
import subprocess
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
        db.session.execute(db.text("SELECT 1"))
        logger.info("Conexão com o banco de dados estabelecida com sucesso!")
except Exception as e:
    logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
    raise

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fullname = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
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
    slug = db.Column(db.String(100), nullable=False, unique=True)
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
    
# Modelo para scripts PowerShell temporários
class PowerShellScript(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    script = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    access_count = db.Column(db.Integer, default=0)
    last_accessed = db.Column(db.DateTime, nullable=True)

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
def slugify(text):
    """Converte texto para slug URL-friendly."""
    import re
    import unicodedata
    
    # Converte para lowercase e remove acentos
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    text = text.lower()
    
    # Remove caracteres não alfanuméricos e substitui por hífen
    text = re.sub(r'[^a-z0-9]+', '-', text)
    
    # Remove hífens duplicados e de início/fim
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    
    return text
    
def get_unique_slug(title, post_id=None):
    """Gera um slug único baseado no título do post."""
    base_slug = slugify(title)
    slug = base_slug
    n = 1
    
    while True:
        # Verifica se o slug existe (excluindo o post atual se estiver editando)
        if post_id:
            existing = Post.query.filter(Post.slug == slug, Post.id != post_id).first()
        else:
            existing = Post.query.filter_by(slug=slug).first()
        
        if not existing:
            return slug
            
        # Se já existe, adiciona um número ao final
        slug = f"{base_slug}-{n}"
        n += 1

def get_publication_date(post):
    """Retorna a data de publicação do post (scheduled_for se disponível, ou created_at)."""
    fuso_sp = pytz.timezone('America/Sao_Paulo')
    
    # Se tem data agendada, essa é a data de publicação
    if post.scheduled_for:
        return post.scheduled_for.astimezone(fuso_sp).strftime('%d/%m/%Y %H:%M')
    
    # Caso contrário, usa a data de criação
    return post.created_at.astimezone(fuso_sp).strftime('%d/%m/%Y %H:%M')

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
        'slug': p.slug,
        'content': p.content,
        'main_image': p.main_image,
        'created_at': get_publication_date(p)  # Agora usa a data de publicação
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

# Registra a função get_publication_date como função template
app.jinja_env.globals.update(get_publication_date=get_publication_date)

# Middleware para registrar acessos às páginas
@app.before_request
def track_page_view():
    # Verificar se é uma das páginas que devemos contabilizar:
    # 1. Página principal (/)
    # 2. Página de post individual (/post/slug)
    # 3. Página de listagem de todos os posts (/posts_all)
    valid_paths = ['/', '/posts_all']
    is_post_page = request.path.startswith('/post/') and not request.path.endswith('/edit') and not request.path.endswith('/delete')
    
    # Contabilizar apenas se for uma das páginas desejadas
    if not (request.path in valid_paths or is_post_page):
        return
    
    # Ignorar recursos estáticos, favicon ou a própria página de analytics
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
        device_type = ('Mobile' if user_agent.is_mobile else 
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

@app.route('/post/<slug>')
def post_view(slug):
    # Busca o post pelo slug
    post = Post.query.filter_by(slug=slug).first_or_404()
    post_id = post.id
    
    # Tenta buscar do cache primeiro
    cache_key = f'post_{post_id}'
    cached_post = mc.get(cache_key)
    cached_comments = mc.get(f'comments_{post_id}')
    
    if cached_post is None:
        post_dict = {
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'content': post.content,
            'main_image': post.main_image,
            'created_at': get_publication_date(post),  # Agora usa a data de publicação
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

        # Gerar um slug único para o post
        slug = get_unique_slug(title)

        file = request.files.get('main_image')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_post = Post(
            title=title, 
            content=content, 
            slug=slug,
            main_image=filename, 
            is_published=False, 
            user_id=current_user.id
        )

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
        title = request.form['title']
        post.title = title
        post.content = request.form['content']

        # Atualizar o slug apenas se o título mudou
        if slugify(post.title) != slugify(title):
            post.slug = get_unique_slug(title, post_id)

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

@app.route('/post/<slug>/comment', methods=['POST'])
@login_required
def add_comment(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    post_id = post.id
    
    content = request.form.get('content')
    if not content:
        flash('Comentário vazio não vale! 😅', 'danger')
        return redirect(url_for('post_view', slug=slug))
    comment = Comment(post_id=post_id, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()
    
    # Invalida o cache de comentários
    mc.delete(f'comments_{post_id}')
    
    flash('Comentário adicionado!', 'success')
    return redirect(url_for('post_view', slug=slug))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form['password']
        confirm_password = request.form.get('confirm_password')
        
        # Validações
        if not fullname or not email:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('As senhas não conferem.', 'danger')
            return render_template('register.html')
        
        # Verifica se o usuário ou e-mail já existem
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            if existing_user.username == username:
                flash('Esse nome de usuário já está sendo utilizado.', 'danger')
            else:
                flash('Esse e-mail já está registrado.', 'danger')
            return render_template('register.html')
        
        # Cria o novo usuário
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username, 
            password=hashed_password, 
            fullname=fullname, 
            email=email, 
            phone=phone,
            role='user'
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registro realizado com sucesso! Faça login para continuar. 😉', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro ao registrar seu usuário. Tente novamente.', 'danger')
            
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            flash(f'Bem-vindo de volta, {user.fullname or user.username}!', 'success')
            return redirect(url_for('admin' if user.role=='admin' else 'home'))
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
          <link>https://chiapettadev.site/post/{{p.slug}}</link>
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

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/powershell')
@admin_required
def powershell():
    return render_template('powershell.html')

# Função removida - não permite mais criar scripts personalizados

@app.route('/ps/<token>')
def access_ps_script(token):
    # Verificar se é o token especial para modo escuro
    if token == 'dark-mode':
        # Script de modo escuro fixo
        dark_mode_script = """# Script para ativar modo escuro no Windows
# Execute como Administrador

# Ativar tema escuro do sistema
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "SystemUsesLightTheme" -Value 0

# Ativar tema escuro dos apps
Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "AppsUseLightTheme" -Value 0

# Forçar atualização das configurações
rundll32.exe user32.dll,UpdatePerUserSystemParameters

Write-Host "Modo escuro ativado com sucesso!" -ForegroundColor Green
Write-Host "Pode ser necessário reiniciar algumas aplicações para aplicar as mudanças." -ForegroundColor Yellow
"""
        # Registrar o acesso (opcional)
        try:
            # Buscar ou criar um registro para este script fixo
            script = PowerShellScript.query.filter_by(token='dark-mode').first()
            if not script:
                # Criar um registro permanente para o script de modo escuro
                script = PowerShellScript(
                    token='dark-mode',
                    script=dark_mode_script,
                    description='Script para ativar modo escuro no Windows',
                    expires_at=datetime.now() + timedelta(days=365*10),  # 10 anos (praticamente permanente)
                    created_by=1  # Considerando que o ID 1 é o admin
                )
                db.session.add(script)
            
            # Atualizar contadores
            script.access_count += 1
            script.last_accessed = datetime.now()
            db.session.commit()
        except Exception as e:
            logger.error(f"Erro ao registrar acesso ao script de modo escuro: {str(e)}")
        
        # Retornar o script como texto puro
        return Response(dark_mode_script, mimetype='text/plain')
    
    # Para outros tokens, buscar no banco de dados (mantido para compatibilidade)
    script = PowerShellScript.query.filter_by(token=token).first()
    
    # Verificar se o script existe
    if not script:
        abort(404)
    
    # Verificar se o script não expirou
    if script.expires_at < datetime.now():
        return "Este script expirou", 410
    
    # Atualizar contadores
    script.access_count += 1
    script.last_accessed = datetime.now()
    db.session.commit()
    
    # Retornar o script como texto puro (para ser executado diretamente)
    return Response(script.script, mimetype='text/plain')

@app.route('/powershell/list')
@admin_required
def list_ps_scripts():
    scripts = PowerShellScript.query.filter_by(created_by=current_user.id).order_by(PowerShellScript.created_at.desc()).all()
    
    scripts_data = [{
        'id': s.id,
        'token': s.token,
        'description': s.description,
        'created_at': s.created_at.strftime('%d/%m/%Y %H:%M'),
        'expires_at': s.expires_at.strftime('%d/%m/%Y %H:%M'),
        'access_count': s.access_count,
        'last_accessed': s.last_accessed.strftime('%d/%m/%Y %H:%M') if s.last_accessed else 'Nunca',
        'active': s.expires_at > datetime.now()
    } for s in scripts]
    
    return jsonify({'scripts': scripts_data})

@app.route('/admin')
@admin_required
def admin():
    # Estatísticas rápidas para o painel admin
    total_posts = Post.query.count()
    published_posts = Post.query.filter_by(is_published=True).count()
    draft_posts = Post.query.filter_by(is_published=False).count()
    
    # Último post publicado
    last_post = Post.query.filter_by(is_published=True).order_by(Post.created_at.desc()).first()
    
    # Atividade recente - últimas visualizações
    recent_views = PageView.query.order_by(PageView.timestamp.desc()).limit(10).all()
    
    # Comentários recentes
    recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(5).all()
    
    # Data e hora atual em São Paulo
    fuso_sp = pytz.timezone('America/Sao_Paulo')
    current_time = datetime.now(fuso_sp)
    
    return render_template(
        'admin.html', 
        user=current_user,
        total_posts=total_posts,
        published_posts=published_posts,
        draft_posts=draft_posts,
        last_post=last_post,
        recent_views=recent_views,
        recent_comments=recent_comments,
        current_time=current_time
    )

@app.route('/admin_stats')
@admin_required
def admin_stats():
    # Contagem de posts
    total_posts = Post.query.count()
    
    # Contagem de visualizações
    total_views = PageView.query.count()
    
    # Contagem de usuários registrados
    total_users = User.query.count()
    
    return jsonify({
        'posts': total_posts,
        'views': total_views,
        'users': total_users
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=7000, threaded=True)
