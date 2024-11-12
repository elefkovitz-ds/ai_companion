from flask_wtf import FlaskForm
from flask import request
from wtforms import StringField, SubmitField, TextAreaField, RadioField
from wtforms.validators import ValidationError, DataRequired, Length
import sqlalchemy as sa
from flask_babel import _, lazy_gettext as _l
from app import db
from app.models import User


class EditProfileForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    about_me = TextAreaField(_l('About me'),
                             validators=[Length(min=0, max=140)])
    submit = SubmitField(_l('Submit'))

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = db.session.scalar(sa.select(User).where(
                User.username == username.data))
            if user is not None:
                raise ValidationError(_('Please use a different username.'))

class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')

class CreateCompanionForm(FlaskForm):
    #consider also: SelectField (more custom, more manual work)
    gender = RadioField(_l('Gender'), choices=['Male', 'Female', 'Other'], validators=[DataRequired()])
    realism = RadioField(_l('Real or Animated'), choices=['Realistic', 'Anime', 'AI-generated'], validators=[DataRequired()])
    companion_name = TextAreaField(_l('Name Your Companion:'), validators=[DataRequired(), Length(min=1, max=40)])
    submit = SubmitField(_l('Submit'))

class SearchForm(FlaskForm):
    q = StringField(_l('Search'), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'meta' not in kwargs:
            kwargs['meta'] = {'csrf': False}
        super(SearchForm, self).__init__(*args, **kwargs)