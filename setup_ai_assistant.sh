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
