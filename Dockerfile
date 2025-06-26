# Base Image - Python 3.13 (or whatever version you are using)
FROM python:3.13-slim-buster

# Set environment variables for Python
ENV PYTHONUNBUFFERED 1

# Set the working directory inside the container
# This should be the directory where manage.py is located
# Based on your structure, this should be the root of the repo
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the entire project code into the container
# This will copy manage.py, growthflow_backend/, feedback_app/, etc.
COPY . /app/

# Expose the port Gunicorn will listen on
EXPOSE $PORT

# Command to run the application using Gunicorn
# Ensure 'growthflow_backend' is the correct folder name
# And ensure the working directory is set correctly above
CMD ["gunicorn", "growthflow_backend.wsgi:application", "--bind", "0.0.0.0:$PORT"]
