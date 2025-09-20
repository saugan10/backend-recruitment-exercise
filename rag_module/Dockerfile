# rag_module/Dockerfile

# 1. Use an official Python runtime as a parent image.
# Using a slim version keeps the final image size smaller.
FROM python:3.11-slim

# 2. Set the working directory inside the container.
WORKDIR /app

# 3. Copy the requirements file into the container at /app.
# This is done first to leverage Docker's layer caching.
# If requirements.txt doesn't change, this layer won't be rebuilt.
COPY requirements.txt .

# 4. Install any needed packages specified in requirements.txt.
# --no-cache-dir reduces the image size.
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application's code into the container.
# This includes main.py, services.py, etc.
COPY . .

# 6. Expose the port the app runs on.
EXPOSE 8001

# 7. Define the command to run the application.
# The --host 0.0.0.0 makes the server accessible from outside the container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]