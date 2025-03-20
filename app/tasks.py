import time
import sys
import json
import signal
import sqlalchemy as sa
from flask import render_template
from rq import get_current_job
from app import create_app, db
from app.models import User, Companion, Task
from app.email import send_email
#from app.errors import errors
from app.errors.errors import TimeoutException
from datetime import datetime

app = create_app()
app.app_context().push()

def _set_task_progress(progress):
    app.logger.info('Setting task progress...')
    app.logger.info('Setting task progress...')
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
        app.logger.info('Progress for Redis job_id {0} updated to {1}'.format(job.get_id(), progress))


# dummy function to export all companions a user has. Not useful in itself, but code will be!
# eventually switch this to export chat history
def export_companions(user_id, max_runtime=120):
    try:
        app.logger.info('Exporting companions for user_id {0}'.format(user_id))
        signal.alarm(max_runtime)
        #start_time = datetime.now()
        user = db.session.get(User, user_id)
        _set_task_progress(0)
        app.logger.info('Setting export_companion progress to 0')
        data = []
        i = 0
        companion_list = db.session.scalar(sa.select(sa.func.count()).select_from(
            user.companions.select().subquery()))
        app.logger.info('Companion list pulled successfully')
        for comp in db.session.scalars(user.companions.select().order_by(
                Companion.created_at_ts.asc())):
            data.append({'name': comp.companion_name,
                         'timestamp': comp.created_at_ts.isoformat() + 'Z'})
            time.sleep(5)
            i += 1
            _set_task_progress(100 * i // companion_list)
        app.logger.info('Companion list successfully generated in list form to send email')
        app.logger.info('Now ensuring email params are set correctly...')
        app.logger.info('Sender: {0} Recipient: {1}...should be enough'.format(app.config['ADMINS'][0], [user.email]))
        send_email(
            '[AICompanion] Your created companions:',
            sender=app.config['ADMINS'][0], recipients=[user.email],
            text_body=render_template('email/export_companions.txt', user=user),
            html_body=render_template('email/export_companions.html', user=user),
            attachments=[('companions.json', 'application/json',
                          json.dumps({'companions': data}, indent=4))],
            sync=True)
        #runtime = timedelta(seconds=datetime.now() - start_time)
        #app.logger.info('Runtime for this is {0}'.format(runtime))
        #if (runtime > max_runtime):
        #    raise MaxRuntimeException:
        #        _set_task_progress(100)
        #        app.logger.error('Runtime exceeds maximum runtime of {0} seconds, cancelling job and exiting.'.format(max_runtime), exc_info=sys.exc_info())
    except TimeoutException:
        _set_task_progress(100)
        app.logger.error('Runtime exceeds maximum runtime of {0} seconds, cancelling job and exiting.'.format(max_runtime), exc_info=sys.exc_info())
    except Exception:
        _set_task_progress(100)
        app.logger.error('Unhandled exception', exc_info=sys.exc_info())
    finally:
        app.logger.info('Export companion function successfully completed for user {0}'.format(user_id))
        _set_task_progress(100)
        signal.alarm(0)