# Use an official Python runtime
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy local code to the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run your bot
CMD ["python", "main.py"]
