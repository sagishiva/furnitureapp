# Use an official Python runtime as a parent image
FROM python:3.11.6

# Set the working directory in the container
WORKDIR /

# Step 1: Upgrade pip, setuptools, and wheel
RUN python -m pip install --upgrade pip setuptools wheel

# Step 2: Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 3: Copy the entire project code
COPY . .

# Step 4: Make migrations and migrate
RUN python manage.py makemigrations
RUN python manage.py migrate

# Make port 8000 available to the world outside this container
# EXPOSE 8000

# Set the environment variable for Django
ENV DJANGO_SETTINGS_MODULE=furnitureapp.settings

# Use Gunicorn to serve the application
CMD ["gunicorn", "furnitureapp.wsgi:application", "--bind", "0.0.0.0:$PORT"]

# # Run the application
# CMD ["python", "manage.py", "runserver", "0.0.0.0:5000"]
