from flask import render_template, flash, redirect, url_for, request, g
from flask_login import current_user, login_user, login_required, logout_user
from flask_babel import _, get_locale
from langdetect import detect, LangDetectException
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, CreateCompanionForm, ResetPasswordRequestForm, ResetPasswordForm
from app.models import User, Companion
from app.email import send_password_reset_email
from urllib.parse import urlsplit
from datetime import datetime, timezone
import sqlalchemy as sa

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
    g.locale = str(get_locale())

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = CreateCompanionForm()
    if form.validate_on_submit():
        try:
            language = detect(form.message.data)
        except LangDetectException:
            language = ''
        companion = Companion(gender=form.gender.data, realism=form.realism.data, companion_name=form.companion_name.data, creator=current_user, language=language)
        db.session.add(companion)
        db.session.commit()
        flash(_('Your new AI Companion has been created!'))
        return redirect(url_for('index'))
    companions = db.session.scalars(sa.Select(Companion).where(Companion.associated_user_id == current_user.id)).all()
    return render_template("index.html", title='Home', form=form, companions=companions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    #validate if user is logged in or not, send them to homepage if successful
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    #login process & error handling
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash(_('Invalid email or password'))
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(_('Congratulations, you are now a registered user!'))
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash(_('Check your email for the instructions to reset your password'))
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash(_('Your password has been reset.'))
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    companions = db.session.scalars(sa.Select(Companion).where(Companion.associated_user_id == current_user.id)).all()
    return render_template('user.html', user=user, companions=companions)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',form=form)