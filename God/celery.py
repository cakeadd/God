import os

from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'God.settings')

app = Celery('God')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
