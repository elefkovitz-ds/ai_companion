from flask import current_app, render_template
from app import db
from app.errors import bp

@bp.app_errorhandler(404)
def not_found_error(error):
    current_app.logger.error(error, exc_info=True)
    return render_template('errors/404.html'), 404

@bp.app_errorhandler(500)
def internal_error(error):
    current_app.logger.error(error, exc_info=True)
    db.session.rollback()
    return render_template('errors/500.html'), 500

@bp.app_errorhandler(Exception)
def generic_error(error):
    current_app.logger.error(error, exc_info=True)