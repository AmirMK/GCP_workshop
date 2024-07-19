# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the local files to the container
COPY . /app

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt


# Set the entrypoint
ENTRYPOINT ["python", "ad_placement_analysis.py"]
