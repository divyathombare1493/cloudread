from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired

class AddBookForm(FlaskForm):
    ebook_name = StringField('Book Name', validators=[DataRequired()])
    ebook_category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    ebook_pdf = FileField('PDF File', validators=[FileRequired(), FileAllowed(['pdf'], 'PDF only')])
    ebook_cover = FileField('Cover Image', validators=[FileRequired(), FileAllowed(['jpg', 'jpeg', 'png'], 'Images only')])
    submit = SubmitField('Add Book')
