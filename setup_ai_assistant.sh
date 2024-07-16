#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define variables
PGPASSWORD=gcpworkshop2024
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1
ADBCLUSTER=alloydb-aip-01
INSTANCE_NAME=instance-1
ZONE=us-central1-c

echo "Starting the setup process..."

# Inside the VM

# Install PostgreSQL client
echo "Installing PostgreSQL client..."
sudo apt-get update
sudo apt-get install --yes postgresql-client
echo "PostgreSQL client installed."

# Set environment variables for PostgreSQL connection
export PGPASSWORD=gcpworkshop2024
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1
export ADBCLUSTER=alloydb-aip-01
export INSTANCE_IP=$(gcloud alloydb instances describe $ADBCLUSTER-pr --cluster=$ADBCLUSTER --region=$REGION --format="value(ipAddress)")

echo "Environment variables set."

# Connect to the AlloyDB instance and create database
echo "Connecting to AlloyDB instance and creating database..."
psql "host=$INSTANCE_IP user=postgres sslmode=require" -c "CREATE DATABASE assistantdemo"
psql "host=$INSTANCE_IP user=postgres dbname=assistantdemo" -c "CREATE EXTENSION vector"
echo "Database created and pgVector extension enabled."

# Install required packages for Python
echo "Installing required packages for Python..."
sudo apt install -y git build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
echo "Required packages for Python installed."

# Install pyenv
echo "Installing pyenv..."
curl https://pyenv.run | bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
source ~/.bashrc
echo "pyenv installed."

# Install Python 3.11.6
echo "Installing Python 3.11.6..."
pyenv install 3.11.6
pyenv global 3.11.6
python -V
echo "Python 3.11.6 installed."

# Clone the GitHub repository
echo "Cloning the GitHub repository..."
git clone https://github.com/getrakeshthakur/genai-databases-retrieval-app.git
echo "GitHub repository cloned."

# Configure and initialize the database
echo "Configuring and initializing the database..."
cd genai-databases-retrieval-app/retrieval_service
cp example-config.yml config.yml
sed -i s/127.0.0.1/$INSTANCE_IP/g config.yml
sed -i s/my-password/$PGPASSWORD/g config.yml
sed -i s/my_database/assistantdemo/g config.yml
sed -i s/my-user/postgres/g config.yml
cat config.yml
echo "Database configured."

# Install Python dependencies and initialize the database
echo "Installing Python dependencies and initializing the database..."
pip install -r requirements.txt
python run_database_init.py
echo "Python dependencies installed and database initialized."

# Create a service account and deploy the extension service to Cloud Run
echo "Creating a service account and deploying the extension service to Cloud Run..."
gcloud iam service-accounts create retrieval-identity
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:retrieval-identity@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

cd ~/genai-databases-retrieval-app
gcloud alpha run deploy retrieval-service \
    --source=./retrieval_service/ \
    --no-allow-unauthenticated \
    --service-account retrieval-identity \
    --region us-central1 \
    --network=default \
    --quiet
echo "Service account created and extension service deployed to Cloud Run."

# Prepare the environment and run the assistant application
echo "Preparing the environment and running the assistant application..."
cd ~/genai-databases-retrieval-app/llm_demo
pip install -r requirements.txt
export BASE_URL=$(gcloud run services list --filter="(retrieval-service)" --format="value(URL)")
export ORCHESTRATION_TYPE=langchain-tools
python run_app.py
echo "Assistant application running."
