from rq import get_current_job
from app import create_app, db
from app.models import Task
from app.email import send_email
import time
import sys
import json
from flask import render_template


app = create_app()
app.app_context().push()

def example(seconds):
    job = get_current_job()
    print('Starting task')
    for i in range(seconds):
        job.meta['progress'] = 100.0 * i / seconds
        job.save_meta()
        print(i)
        time.sleep(1)
    job.meta['progress'] = 100
    job.save_meta()
    print('Task completed')

def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        task = db.session.get(Task, job.get_id())
        task.user.add_notification('task_progress', {'task_id': job.get_id(),
                                                     'progress': progress})
        if progress >= 100:
            task.complete = True
        db.session.commit()

# dummy function to export all companions a user has. Not useful in itself, but code will be!
# eventually switch this to export chat history
def export_companions(user_id):
    try:
        user = db.session.get(User, user_id)
        _set_task_progress(0)
        data = []
        i = 0
        companion_list = db.session.scalar(sa.select(sa.func.count()).select_from(
            user.companions.select().subquery()))
        for comp in db.session.scalars(user.companions.select().order_by(
                Companion.created_at_ts.asc())):
            data.append({'name': comp.companion_name,
                         'timestamp': comp.created_at_ts.isoformat() + 'Z'})
            time.sleep(5)
            i += 1
            _set_task_progress(100 * i // companion_list)

        send_email(
            '[AICompanion] Your created companions:',
            sender=app.config['ADMINS'][0], recipients=[user.email],
            text_body=render_template('email/export_companions.txt', user=user),
            html_body=render_template('email/export_companions.html', user=user),
            attachments=[('companions.json', 'application/json',
                          json.dumps({'companions': data}, indent=4))],
            sync=True)
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
    finally:
        _set_task_progress(100)