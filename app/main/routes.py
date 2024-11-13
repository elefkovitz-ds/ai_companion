from datetime import datetime, timezone
from flask import render_template, flash, redirect, url_for, request, g, \
    current_app
from flask_login import current_user, login_required
from flask_babel import _, get_locale
import sqlalchemy as sa
from langdetect import detect, LangDetectException
from app import db
from app.main.forms import EditProfileForm, EmptyForm, CreateCompanionForm, SearchForm
from app.models import User, Companion, Message
#we havent built this one yet (no free translate API sadge)
#from app.translate import translate
from app.main import bp

@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = CreateCompanionForm()
    if form.validate_on_submit():
        # This code technically works, but there's nothing for it to search for.
        # It searches for message in the form, but the CreateCompanionForm doesn't have a field called "message" so it errors out
        # This isn't necessarily a "bug", more so that I just haven't built the features/structure that make it work. But it should when it's time!
        #try:
        #    language = detect(form.message.data)
        #except LangDetectException:
        #    language = ''
        companion = Companion(gender=form.gender.data, realism=form.realism.data, companion_name=form.companion_name.data, creator=current_user)
        #we ain't done this yet
        #, language=language)
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

@bp.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    companions = db.session.scalars(sa.select(Companion).join(User.companions).where(User.username == username).order_by(Companion.created_at_ts)).all()
    form = EmptyForm()
    return render_template('user_popup.html', user=user, form=form, companions=companions)

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

#currently not implemented!
@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    data = request.get_json()
    return {'text': translate(data['text'],
                              data['source_language'],
                              data['dest_language'])}

@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type=int)
    posts, total = Message.search(g.search_form.q.data, page,
                               current_app.config['ITEMS_PER_PAGE'])
    next_url = url_for('main.search', q=g.search_form.q.data, page=page + 1) \
        if total > page * current_app.config['ITEMS_PER_PAGE'] else None
    prev_url = url_for('main.search', q=g.search_form.q.data, page=page - 1) \
        if page > 1 else None
    return render_template('search.html', title=_('Search'), posts=posts,
                           next_url=next_url, prev_url=prev_url)