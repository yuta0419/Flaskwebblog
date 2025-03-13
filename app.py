import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_ckeditor import CKEditor, CKEditorField, upload_success, upload_fail
from wtforms import StringField, FileField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
from PIL import Image
import pillow_heif

# HEIC形式の画像を扱えるようにする
pillow_heif.register_heif_opener()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
# CKEditor の設定（fullパッケージとアップローダーの指定）
app.config['CKEDITOR_PKG_TYPE'] = 'full'
app.config['CKEDITOR_FILE_UPLOADER'] = 'upload'

db = SQLAlchemy(app)
ckeditor = CKEditor(app)

# -------------------------------
# モデル定義
# -------------------------------
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    tags = db.Column(db.String(200), nullable=True)
    # CKEditor によるリッチテキスト（画像挿入も可能）
    content = db.Column(db.Text, nullable=False)
    # サムネイル画像（投稿時に別途設定）
    thumbnail_filename = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)

# コメントモデル
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author = db.Column(db.String(50), default='Anonymous')
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post = db.relationship('Post', backref=db.backref('comments', lazy=True))

# -------------------------------
# フォーム定義
# -------------------------------
class PostForm(FlaskForm):
    title = StringField('タイトル', validators=[DataRequired()])
    category = StringField('カテゴリー')
    tags = StringField('タグ (カンマ区切り)')
    # CKEditorField を利用して本文をリッチテキストで入力
    content = CKEditorField('本文', validators=[DataRequired()])
    # サムネイル画像を別途設定するフィールド
    thumbnail = FileField('サムネイル画像 (任意)')
    submit = SubmitField('投稿')

class LoginForm(FlaskForm):
    password = PasswordField('パスワード', validators=[DataRequired()])
    submit = SubmitField('ログイン')

ADMIN_PASSWORD = 'admin123'

# -------------------------------
# CKEditor 画像アップロード用ルート
# -------------------------------
@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('upload')
    if not f:
        return upload_fail("ファイルがありません")
    filename = secure_filename(f.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(filepath)
    url = url_for('static', filename='uploads/' + filename)
    return upload_success(url, filename)

# -------------------------------
# 管理者ログイン
# -------------------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    if form.validate_on_submit():
        if form.password.data == ADMIN_PASSWORD:
            session['admin'] = True
            flash('ログインに成功しました', 'success')
            return redirect(url_for('create_post'))
        else:
            flash('パスワードが間違っています', 'danger')
    return render_template('login.html', form=form)

# -------------------------------
# 投稿作成（管理者専用）
# -------------------------------
@app.route('/admin/create', methods=['GET', 'POST'])
def create_post():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    form = PostForm()
    if form.validate_on_submit():
        # サムネイル画像の処理
        thumbnail_file = form.thumbnail.data
        thumb_filename = None
        if thumbnail_file:
            original_filename = secure_filename(thumbnail_file.filename)
            ext = original_filename.rsplit('.', 1)[-1].lower()
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            if ext in ['heic', 'heif']:
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
                thumbnail_file.save(temp_path)
                pil_image = Image.open(temp_path)
                thumb_filename = f"{original_filename.rsplit('.', 1)[0]}.jpg"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], thumb_filename)
                pil_image.save(save_path, format='JPEG')
                os.remove(temp_path)
            else:
                thumb_filename = original_filename
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], thumb_filename)
                thumbnail_file.save(save_path)
        post = Post(
            title=form.title.data,
            category=form.category.data,
            tags=form.tags.data,
            content=form.content.data,
            thumbnail_filename=thumb_filename
        )
        db.session.add(post)
        db.session.commit()
        flash('記事が作成されました', 'success')
        return redirect(url_for('index'))
    return render_template('create_post.html', form=form)

# -------------------------------
# 投稿編集（管理者専用）
# -------------------------------
@app.route('/admin/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    post = Post.query.get_or_404(post_id)
    form = PostForm(obj=post)
    if form.validate_on_submit():
        post.title = form.title.data
        post.category = form.category.data
        post.tags = form.tags.data
        post.content = form.content.data
        # サムネイル画像の更新（入力があれば）
        thumbnail_file = form.thumbnail.data
        if thumbnail_file:
            original_filename = secure_filename(thumbnail_file.filename)
            ext = original_filename.rsplit('.', 1)[-1].lower()
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            if ext in ['heic', 'heif']:
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
                thumbnail_file.save(temp_path)
                new_thumb_filename = f"{original_filename.rsplit('.', 1)[0]}.jpg"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_thumb_filename)
                pil_image = Image.open(temp_path)
                pil_image.save(save_path, format='JPEG')
                os.remove(temp_path)
            else:
                new_thumb_filename = original_filename
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_thumb_filename)
                thumbnail_file.save(save_path)
            post.thumbnail_filename = new_thumb_filename
        db.session.commit()
        flash('記事が更新されました', 'success')
        return redirect(url_for('view_post', post_id=post.id))
    return render_template('create_post.html', form=form)

# -------------------------------
# 記事詳細表示
# -------------------------------
@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', post=post)

# -------------------------------
# 記事一覧（ホーム）
# -------------------------------
@app.route('/')
def index():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts)

# -------------------------------
# 管理者ログアウト
# -------------------------------
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('ログアウトしました', 'success')
    return redirect(url_for('index'))

# -------------------------------
# キーワード検索（タイトルおよび本文を対象）
# -------------------------------
@app.route('/search')
def search():
    q = request.args.get('q', '')
    posts = []
    if q:
        posts = Post.query.filter(
            (Post.title.contains(q)) | (Post.content.contains(q))
        ).order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts, filter_title=f"検索結果: {q}")

# -------------------------------
# カテゴリーでフィルタリング
# -------------------------------
@app.route('/category/<category_name>')
def filter_by_category(category_name):
    posts = Post.query.filter(Post.category == category_name).order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts, filter_title=f"カテゴリー: {category_name}")

# -------------------------------
# タグでフィルタリング
# -------------------------------
@app.route('/tag/<tag_name>')
def filter_by_tag(tag_name):
    posts = Post.query.filter(Post.tags.like(f"%{tag_name}%")).order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts, filter_title=f"タグ: {tag_name}")

# -------------------------------
# いいね機能（POSTメソッド）
# -------------------------------
@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.likes += 1
    db.session.commit()
    return redirect(url_for('view_post', post_id=post_id))

# -------------------------------
# コメント追加（POSTメソッド）
# -------------------------------
@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    author = request.form.get('author', 'Anonymous')
    content = request.form.get('content', '')
    if not content:
        flash('コメントの内容を入力してください', 'danger')
        return redirect(url_for('view_post', post_id=post_id))
    comment = Comment(post_id=post_id, author=author, content=content)
    db.session.add(comment)
    db.session.commit()
    flash('コメントが追加されました', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/admin/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not session.get('admin'):
        flash('削除する権限がありません', 'danger')
        return redirect(url_for('index'))
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('記事が削除されました', 'success')
    return redirect(url_for('index'))


# -------------------------------
# メイン処理
# -------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
