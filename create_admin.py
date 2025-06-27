# create_admin.py
import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings') # Change 'your_project_name.settings' to 'settings'
django.setup()

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin') # Get from env var or default
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'your_secure_password')

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser: {username}")
    User.objects.create_superuser(username, email, password)
    print("Superuser created successfully.")
else:
    print(f"Superuser '{username}' already exists.")
