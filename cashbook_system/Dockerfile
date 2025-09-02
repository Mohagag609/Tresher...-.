FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create database
RUN python3 simple_init.py

# Expose port
EXPOSE 5000

# Run application
CMD ["python3", "simple_run.py"]