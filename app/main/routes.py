from datetime import datetime, timezone
from flask import render_template, flash, redirect, url_for, request, g, \
    current_app
from flask_login import current_user, login_required
from flask_babel import _, get_locale
import sqlalchemy as sa
from langdetect import detect, LangDetectException
from app import db
from app.main.forms import EditProfileForm, EmptyForm, CreateCompanionForm
from app.models import User, Companion, Message
#we havent built this one yet (no free translate API sadge)
#from app.translate import translate
from app.main import bp

@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
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
        return redirect(url_for('main.index'))
    companions = db.session.scalars(sa.Select(Companion).where(Companion.associated_user_id == current_user.id)).all()
    return render_template('index.html', title=_('Home'), form=form, companions=companions)

@bp.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    form = EmptyForm()
    return render_template('user.html', user=user, form=form)

@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title=_('Edit Profile'),
                           form=form)