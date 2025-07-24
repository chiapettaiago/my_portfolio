from functools import wraps
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, abort, Response, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pytz
from datetime import datetime, date, timedelta
import os
import logging
import hashlib
import binascii
import scrypt
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

# Pasta de upload e limites
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
CACHE_TIMEOUT = 60 * 15  # 15 minutos

# Configuração do Firebase
# Caminho para o arquivo de credenciais do Firebase
firebase_credentials_path = os.path.join(BASE_DIR, 'firebase_credentials.json')

# Função personalizada para verificar senhas scrypt (migradas do MySQL)
def check_scrypt_password(stored_hash, password):
    """
    Verifica senha contra hash scrypt no formato: scrypt:n:r:p$salt$hash
    Compatível com senhas migradas do MySQL
    """
    if not stored_hash.startswith('scrypt:'):
        # Se não for scrypt, usar verificação padrão do Werkzeug
        return check_password_hash(stored_hash, password)
    
    try:
        # Parse do formato scrypt:n:r:p$salt$hash
        parts = stored_hash.split('$')
        if len(parts) != 3:
            return False
            
        params_and_salt = parts[1]
        stored_hash_hex = parts[2]
        
        # Extrair parâmetros scrypt do formato scrypt:32768:8:1
        params_part = stored_hash.split('$')[0]  # scrypt:32768:8:1
        param_values = params_part.split(':')
        
        if len(param_values) != 4 or param_values[0] != 'scrypt':
            return False
            
        n = int(param_values[1])  # 32768
        r = int(param_values[2])  # 8  
        p = int(param_values[3])  # 1
        
        # Salt está na segunda parte após os parâmetros
        salt = params_and_salt.split(':')[-1]  # Pega tudo após o último ':'
        
        # Gerar hash scrypt da senha fornecida usando a biblioteca scrypt
        password_bytes = password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        
        # Usar a biblioteca scrypt (mais compatível com altos valores de N)
        generated_hash = scrypt.hash(
            password_bytes,
            salt_bytes,
            N=n, r=r, p=p,
            buflen=64
        )
        
        generated_hash_hex = generated_hash.hex()
        
        # Comparar os hashes
        return generated_hash_hex == stored_hash_hex
        
    except Exception as e:
        logger.error(f"Erro ao verificar senha scrypt: {str(e)}")
        return False

# Inicialização do Firebase usando o arquivo de credenciais
try:
    cred = credentials.Certificate(firebase_credentials_path)
    firebase_admin.initialize_app(cred)
    db_firestore = firestore.client()
    logger.info("Firebase inicializado com sucesso!")
except Exception as e:
    logger.error(f"Erro ao inicializar Firebase: {str(e)}")
    logger.warning("Executando em modo de desenvolvimento sem Firebase")
    db_firestore = None

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Extensões
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Teste de conexão inicial
try:
    with app.app_context():
        logger.info("Conexão com o banco de dados estabelecida com sucesso!")
except Exception as e:
    logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
    raise

# Remover SQLAlchemy, PyMySQL, Memcached
# Adicionar helpers para Firestore

def get_firestore_collection(name):
    if db_firestore is None:
        logger.warning(f"Tentativa de acesso à coleção '{name}' sem Firebase configurado")
        return None
    return db_firestore.collection(name)

# Usuário
class User(UserMixin):
    def __init__(self, id, username, password, fullname, email, phone, role):
        self.id = id
        self.username = username
        self.password = password
        self.fullname = fullname
        self.email = email
        self.phone = phone
        self.role = role

    @staticmethod
    def from_dict(doc):
        data = doc.to_dict()
        return User(
            id=doc.id,
            username=data.get('username'),
            password=data.get('password'),
            fullname=data.get('fullname'),
            email=data.get('email'),
            phone=data.get('phone'),
            role=data.get('role', 'user')
        )

# Funções CRUD para User

def get_user_by_id(user_id):
    if db_firestore is None:
        # Dados de exemplo para modo de desenvolvimento
        if user_id == "admin":
            return User(
                id="admin",
                username="admin",
                password=generate_password_hash("admin"),
                fullname="Administrador",
                email="admin@example.com",
                phone="",
                role="admin"
            )
        return None
    
    doc = get_firestore_collection('users').document(user_id).get()
    if doc.exists:
        return User.from_dict(doc)
    return None

def get_user_by_username(username):
    if db_firestore is None:
        # Dados de exemplo para modo de desenvolvimento
        if username == "admin":
            return User(
                id="admin",
                username="admin",
                password=generate_password_hash("admin"),
                fullname="Administrador",
                email="admin@example.com",
                phone="",
                role="admin"
            )
        return None
    
    users = get_firestore_collection('users').where('username', '==', username).stream()
    for doc in users:
        return User.from_dict(doc)
    return None

def get_user_by_email(email):
    users = get_firestore_collection('users').where('email', '==', email).stream()
    for doc in users:
        return User.from_dict(doc)
    return None

# MODELOS FIRESTORE
# User já foi adaptado acima

# Post
class Post:
    def __init__(self, id, title, slug, content, created_at, scheduled_for, is_published, main_image, user_id):
        self.id = id
        self.title = title
        self.slug = slug
        self.content = content
        self.created_at = created_at
        self.scheduled_for = scheduled_for
        self.is_published = is_published
        self.main_image = main_image
        self.user_id = user_id

    @staticmethod
    def from_dict(doc):
        data = doc.to_dict()
        return Post(
            id=doc.id,
            title=data.get('title'),
            slug=data.get('slug'),
            content=data.get('content'),
            created_at=data.get('created_at'),
            scheduled_for=data.get('scheduled_for'),
            is_published=data.get('is_published', False),
            main_image=data.get('main_image'),
            user_id=data.get('user_id')
        )

# Comment
class Comment:
    def __init__(self, id, post_id, user_id, content, created_at):
        self.id = id
        self.post_id = post_id
        self.user_id = user_id
        self.content = content
        self.created_at = created_at

    @staticmethod
    def from_dict(doc):
        data = doc.to_dict()
        return Comment(
            id=doc.id,
            post_id=data.get('post_id'),
            user_id=data.get('user_id'),
            content=data.get('content'),
            created_at=data.get('created_at')
        )

# PageView
class PageView:
    def __init__(self, id, path, ip, user_agent, browser, device_type, referrer, timestamp, user_id):
        self.id = id
        self.path = path
        self.ip = ip
        self.user_agent = user_agent
        self.browser = browser
        self.device_type = device_type
        self.referrer = referrer
        self.timestamp = timestamp
        self.user_id = user_id

    @staticmethod
    def from_dict(doc):
        data = doc.to_dict()
        return PageView(
            id=doc.id,
            path=data.get('path'),
            ip=data.get('ip'),
            user_agent=data.get('user_agent'),
            browser=data.get('browser'),
            device_type=data.get('device_type'),
            referrer=data.get('referrer'),
            timestamp=data.get('timestamp'),
            user_id=data.get('user_id')
        )

# PowerShellScript
class PowerShellScript:
    def __init__(self, id, token, script, description, created_at, expires_at, created_by, access_count, last_accessed):
        self.id = id
        self.token = token
        self.script = script
        self.description = description
        self.created_at = created_at
        self.expires_at = expires_at
        self.created_by = created_by
        self.access_count = access_count
        self.last_accessed = last_accessed

    @staticmethod
    def from_dict(doc):
        data = doc.to_dict()
        return PowerShellScript(
            id=doc.id,
            token=data.get('token'),
            script=data.get('script'),
            description=data.get('description'),
            created_at=data.get('created_at'),
            expires_at=data.get('expires_at'),
            created_by=data.get('created_by'),
            access_count=data.get('access_count', 0),
            last_accessed=data.get('last_accessed')
        )

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

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
        # Verifica se o slug existe no Firestore (excluindo o post atual se estiver editando)
        posts_ref = get_firestore_collection('posts')
        query = posts_ref.where('slug', '==', slug)
        docs = list(query.stream())
        
        # Se não encontrou nenhum ou se o único encontrado é o próprio post
        if not docs or (post_id and len(docs) == 1 and docs[0].id == post_id):
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
    # Usando Firestore para buscar os posts mais recentes
    # Busca diretamente do Firestore, sem cache
    posts = get_published_posts_firestore()[:3]  # Limita a 3 posts
    
    posts_data = [{
        'id': p.id,
        'title': p.title,
        'slug': p.slug,
        'content': p.content,
        'main_image': p.main_image,
        'created_at': get_publication_date(p)  # Agora usa a data de publicação
    } for p in posts]
    
    return posts_data

def publish_scheduled_posts():
    with app.app_context():
        fuso_sp = pytz.timezone('America/Sao_Paulo')
        now = datetime.now(fuso_sp)
        
        # Buscar posts agendados que devem ser publicados
        posts_ref = get_firestore_collection('posts')
        query = posts_ref.where('is_published', '==', False).where('scheduled_for', '<=', now)
        
        for doc in query.stream():
            doc_ref = posts_ref.document(doc.id)
            doc_ref.update({'is_published': True})

# Registra a função get_publication_date como função template
app.jinja_env.globals.update(get_publication_date=get_publication_date)

# Middleware para registrar acessos às páginas
@app.before_request
def track_page_view():
    valid_paths = ['/', '/posts_all']
    is_post_page = request.path.startswith('/post/') and not request.path.endswith('/edit') and not request.path.endswith('/delete')
    if not (request.path in valid_paths or is_post_page):
        return
    if (request.path.startswith('/static') or 
        request.path == '/favicon.ico' or 
        request.path == '/analytics'):
        return
    user_agent_string = request.headers.get('User-Agent', '')
    user_agent = parse(user_agent_string)
    page_view = PageView(
        id=None,
        path=request.path,
        ip=request.remote_addr,
        user_agent=user_agent_string[:255],
        browser=user_agent.browser.family,
        device_type = ('Mobile' if user_agent.is_mobile else 
                       'Tablet' if user_agent.is_tablet else 
                       'PC'),
        referrer=request.referrer[:255] if request.referrer else None,
        timestamp=datetime.now(),
        user_id=current_user.id if current_user.is_authenticated else None
    )
    save_pageview_firestore(page_view)

# Rotas
@app.route('/')
def home():
    skills = ["Python","Flask","HTML","CSS","JavaScript","SQL","Git","Linux","Desenvolvimento Web"]
    recent_posts = get_published_posts_firestore()[:3]
    return render_template('index.html', skills=skills, recent_posts=recent_posts, current_user=current_user)

@app.route('/posts')
@admin_required
def all_posts():
    try:
        # Buscar todos os posts no Firestore, ordenados por data de criação
        posts_ref = get_firestore_collection('posts')
        posts_data = []
        
        for doc in posts_ref.stream():
            try:
                post = Post.from_dict(doc)
                posts_data.append(post)
            except Exception as e:
                logger.error(f"Erro ao processar post {doc.id}: {str(e)}")
                continue
                
        posts = sorted(posts_data, key=lambda p: p.created_at, reverse=True)
        return render_template('all_posts.html', posts=posts)
        
    except Exception as e:
        logger.error(f"Erro na função all_posts: {str(e)}")
        flash('Erro ao carregar posts. Verifique os logs.', 'danger')
        return redirect(url_for('home'))

@app.route('/posts_all')
def posts_all():
    posts = get_published_posts_firestore()
    return render_template('posts_list.html', posts=posts, current_user=current_user)

@app.route('/post/<slug>')
def post_view(slug):
    post_ref = get_firestore_collection('posts').where('slug', '==', slug).stream()
    post = next((Post.from_dict(doc) for doc in post_ref), None)
    if not post:
        abort(404)
    post_id = post.id
    comments = get_comments_by_post_firestore(post_id)
    recent_posts = get_published_posts_firestore()[:3]
    return render_template('post.html', post=post, recent_posts=recent_posts, comments=comments, current_user=current_user)

@app.route('/create', methods=['GET','POST'])
@admin_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        scheduled_date = request.form.get('scheduled_date')
        scheduled_time = request.form.get('scheduled_time')

        slug = slugify(title)

        file = request.files.get('main_image')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_post = Post(
            id=None,
            title=title,
            slug=slug,
            content=content,
            created_at=datetime.now(),
            scheduled_for=None,
            is_published=False,
            main_image=filename,
            user_id=current_user.id
        )

        if scheduled_date and scheduled_time:
            try:
                dt = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
                new_post.scheduled_for = dt
            except ValueError:
                flash('Data ou hora inválida!', 'danger')
                return redirect(url_for('create'))

        save_post_firestore(new_post)
        flash('Post criado com sucesso! 🚀', 'success')
        return redirect(url_for('posts_all'))

    return render_template('create.html')

@app.route('/post/<slug>/edit', methods=['GET','POST'])
@admin_required
def edit_post(slug):
    post_ref = get_firestore_collection('posts').where('slug', '==', slug).stream()
    post = next((Post.from_dict(doc) for doc in post_ref), None)
    if not post:
        abort(404)
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.slug = slugify(post.title)
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
                post.scheduled_for = dt
                post.is_published = False
            except ValueError:
                flash('Data ou hora inválida!', 'danger')
                return redirect(url_for('edit_post', slug=post.slug))
        else:
            post.scheduled_for = None
            post.is_published = True
        save_post_firestore(post)
        flash('Post atualizado com sucesso! 🎉', 'success')
        return redirect(url_for('posts_all'))
    return render_template('edit_post.html', post=post)

@app.route('/post/<slug>/delete', methods=['POST'])
@admin_required
def delete_post(slug):
    post_ref = get_firestore_collection('posts').where('slug', '==', slug).stream()
    post = next((Post.from_dict(doc) for doc in post_ref), None)
    if not post:
        abort(404)
    get_firestore_collection('posts').document(post.id).delete()
    flash('Post excluído com sucesso!', 'success')
    return redirect(url_for('posts_all'))

@app.route('/post/<slug>/comment', methods=['POST'])
@login_required
def add_comment(slug):
    post_ref = get_firestore_collection('posts').where('slug', '==', slug).stream()
    post = next((Post.from_dict(doc) for doc in post_ref), None)
    if not post:
        abort(404)
    post_id = post.id
    content = request.form.get('content')
    if not content:
        flash('Comentário vazio não vale! 😅', 'danger')
        return redirect(url_for('post_view', slug=slug))
    comment = Comment(id=None, post_id=post_id, user_id=current_user.id, content=content, created_at=datetime.now())
    save_comment_firestore(comment)
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
        if get_user_by_username(username):
            flash('Esse nome de usuário já está sendo utilizado.', 'danger')
            return render_template('register.html')
        if get_user_by_email(email):
            flash('Esse e-mail já está registrado.', 'danger')
            return render_template('register.html')
        # Cria o novo usuário
        hashed_password = generate_password_hash(password)
        new_user = User(
            id=None,
            username=username,
            password=hashed_password,
            fullname=fullname,
            email=email,
            phone=phone,
            role='user'
        )
        # Salva no Firestore
        doc_ref = get_firestore_collection('users').document()
        doc_ref.set({
            'username': new_user.username,
            'password': new_user.password,
            'fullname': new_user.fullname,
            'email': new_user.email,
            'phone': new_user.phone,
            'role': new_user.role
        })
        flash('Registro realizado com sucesso! Faça login para continuar. 😉', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = get_user_by_username(request.form['username'])
        if user and check_scrypt_password(user.password, request.form['password']):
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
    # Carrega os posts completos para o feed usando Firestore
    posts = get_published_posts_firestore()[:10]
    
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
    
    # Busca visualizações no período usando Firestore
    pageviews_ref = get_firestore_collection('pageviews')
    query = pageviews_ref.where('timestamp', '>=', start_date).where('timestamp', '<=', end_date)
    
    views = [PageView.from_dict(doc) for doc in query.stream()]
    
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
Set-ItemProperty -Path \"HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize\" -Name \"SystemUsesLightTheme\" -Value 0

# Ativar tema escuro dos apps
Set-ItemProperty -Path \"HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize\" -Name \"AppsUseLightTheme\" -Value 0

# Forçar atualização das configurações
rundll32.exe user32.dll,UpdatePerUserSystemParameters

Write-Host \"Modo escuro ativado com sucesso!\" -ForegroundColor Green
Write-Host \"Pode ser necessário reiniciar algumas aplicações para aplicar as mudanças.\" -ForegroundColor Yellow
"""
        # Registrar o acesso (opcional)
        try:
            # Buscar ou criar um registro para este script fixo
            script_ref = get_firestore_collection('powershellscripts').where('token', '==', 'dark-mode').stream()
            script = next((PowerShellScript.from_dict(doc) for doc in script_ref), None)
            if not script:
                # Criar um registro permanente para o script de modo escuro
                doc_ref = get_firestore_collection('powershellscripts').document()
                doc_ref.set({
                    'token': 'dark-mode',
                    'script': dark_mode_script,
                    'description': 'Script para ativar modo escuro no Windows',
                    'expires_at': datetime.now() + timedelta(days=365*10),
                    'created_by': 1,
                    'access_count': 1,
                    'last_accessed': datetime.now()
                })
            else:
                doc_ref = get_firestore_collection('powershellscripts').document(script.id)
                doc_ref.update({
                    'access_count': script.access_count + 1,
                    'last_accessed': datetime.now()
                })
        except Exception as e:
            logger.error(f"Erro ao registrar acesso ao script de modo escuro: {str(e)}")
        # Retornar o script como texto puro
        return Response(dark_mode_script, mimetype='text/plain')
    
    # Para outros tokens, buscar no banco de dados (mantido para compatibilidade)
    script_ref = get_firestore_collection('powershellscripts').where('token', '==', token).stream()
    script = next((PowerShellScript.from_dict(doc) for doc in script_ref), None)
    if not script:
        abort(404)
    # Verificar se o script não expirou
    if script.expires_at < datetime.now():
        return "Este script expirou", 410
    # Atualizar contadores
    doc_ref = get_firestore_collection('powershellscripts').document(script.id)
    doc_ref.update({
        'access_count': script.access_count + 1,
        'last_accessed': datetime.now()
    })
    # Retornar o script como texto puro (para ser executado diretamente)
    return Response(script.script, mimetype='text/plain')

@app.route('/powershell/list')
@admin_required
def list_ps_scripts():
    # Buscar scripts criados pelo usuário atual usando Firestore
    scripts_ref = get_firestore_collection('powershellscripts')
    query = scripts_ref.where('created_by', '==', current_user.id)
    scripts = sorted([PowerShellScript.from_dict(doc) for doc in query.stream()], 
                    key=lambda s: s.created_at, reverse=True)
    
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

# Exemplo de função para salvar um post no Firestore

def save_post_firestore(post: Post):
    doc_ref = get_firestore_collection('posts').document(post.id if post.id else None)
    doc_ref.set({
        'title': post.title,
        'slug': post.slug,
        'content': post.content,
        'created_at': post.created_at,
        'scheduled_for': post.scheduled_for,
        'is_published': post.is_published,
        'main_image': post.main_image,
        'user_id': post.user_id
    })

# Exemplo de função para buscar posts publicados/agendados

def get_published_posts_firestore():
    if db_firestore is None:
        # Dados de exemplo para modo de desenvolvimento
        return [
            Post(
                id="1",
                title="Post de Exemplo",
                slug="post-de-exemplo",
                content="Este é um post de exemplo para demonstrar a aplicação funcionando sem Firebase.",
                created_at=datetime.now(),
                scheduled_for=None,
                is_published=True,
                main_image=None,
                user_id="admin"
            )
        ]
    
    now = datetime.now()
    posts_ref = get_firestore_collection('posts')
    query = posts_ref.where('is_published', '==', True)
    results = [Post.from_dict(doc) for doc in query.stream()]
    # Adicionar agendados
    agendados = posts_ref.where('scheduled_for', '<=', now).stream()
    for doc in agendados:
        post = Post.from_dict(doc)
        if post not in results:
            results.append(post)
    results.sort(key=lambda p: p.created_at, reverse=True)
    return results

# Exemplo de função para salvar comentários

def save_comment_firestore(comment: Comment):
    doc_ref = get_firestore_collection('comments').document(comment.id if comment.id else None)
    doc_ref.set({
        'post_id': comment.post_id,
        'user_id': comment.user_id,
        'content': comment.content,
        'created_at': comment.created_at
    })

# Exemplo de função para buscar comentários de um post

def get_comments_by_post_firestore(post_id):
    comments_ref = get_firestore_collection('comments')
    query = comments_ref.where('post_id', '==', post_id)
    return [Comment.from_dict(doc) for doc in query.stream()]

# Exemplo de função para salvar visualização de página

def save_pageview_firestore(pageview: PageView):
    if db_firestore is None:
        logger.info(f"PageView registrada (modo dev): {pageview.path} - {pageview.ip}")
        return
    
    doc_ref = get_firestore_collection('pageviews').document()
    doc_ref.set({
        'path': pageview.path,
        'ip': pageview.ip,
        'user_agent': pageview.user_agent,
        'browser': pageview.browser,
        'device_type': pageview.device_type,
        'referrer': pageview.referrer,
        'timestamp': pageview.timestamp,
        'user_id': pageview.user_id
    })

# Tratamento de erros personalizado
@app.errorhandler(400)
def bad_request(e):
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Requisição Inválida</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                .error-box { max-width: 500px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
                .error-code { font-size: 72px; color: #d9534f; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="error-box">
                <div class="error-code">400</div>
                <h1>Requisição Inválida</h1>
                <p>O servidor não conseguiu entender esta requisição.</p>
                <p><a href="/">Voltar à página inicial</a></p>
            </div>
        </body>
        </html>
        """), 400

@app.errorhandler(403)
def forbidden(e):
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Acesso Negado</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                .error-box { max-width: 500px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
                .error-code { font-size: 72px; color: #d9534f; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="error-box">
                <div class="error-code">403</div>
                <h1>Acesso Negado</h1>
                <p>Você não tem permissão para acessar este recurso.</p>
                <p><a href="/">Voltar à página inicial</a></p>
            </div>
        </body>
        </html>
        """), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Página Não Encontrada</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                .error-box { max-width: 500px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
                .error-code { font-size: 72px; color: #d9534f; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="error-box">
                <div class="error-code">404</div>
                <h1>Página Não Encontrada</h1>
                <p>A página que você está procurando não existe.</p>
                <p><a href="/">Voltar à página inicial</a></p>
            </div>
        </body>
        </html>
        """), 404

@app.errorhandler(500)
def internal_server_error(e):
    # Registrar o erro no log
    logger.error(f"Erro 500: {str(e)}")
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Erro Interno do Servidor</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                .error-box { max-width: 500px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
                .error-code { font-size: 72px; color: #d9534f; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="error-box">
                <div class="error-code">500</div>
                <h1>Erro Interno do Servidor</h1>
                <p>Ocorreu um erro ao processar sua requisição. Tente novamente mais tarde.</p>
                <p><a href="/">Voltar à página inicial</a></p>
            </div>
        </body>
        </html>
        """), 500

@app.route('/admin')
@admin_required
def admin_panel():
    from datetime import datetime
    # Dados para o painel (exemplo básico, ajuste conforme necessário)
    user = current_user
    current_time = datetime.now()
    # Estatísticas
    posts_ref = get_firestore_collection('posts')
    posts = [Post.from_dict(doc) for doc in posts_ref.stream()]
    total_posts = len(posts)
    published_posts = len([p for p in posts if p.is_published])
    draft_posts = len([p for p in posts if not p.is_published and not p.scheduled_for])
    last_post = posts[0] if posts else None
    # Comentários recentes
    comments_ref = get_firestore_collection('comments')
    recent_comments = [Comment.from_dict(doc) for doc in comments_ref.stream()]
    # Visualizações recentes
    views_ref = get_firestore_collection('pageviews')
    recent_views = [PageView.from_dict(doc) for doc in views_ref.stream()]
    return render_template('admin.html', user=user, current_time=current_time, total_posts=total_posts, published_posts=published_posts, draft_posts=draft_posts, last_post=last_post, recent_comments=recent_comments, recent_views=recent_views)

if __name__ == '__main__':
    # Não é necessário criar tabelas no Firestore
    app.run(
        host='0.0.0.0', 
        port=7000, 
        threaded=True,
        debug=False
    )
