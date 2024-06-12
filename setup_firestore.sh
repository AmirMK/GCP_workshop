#!/bin/bash

# Function to print usage
usage() {
    echo "Usage: $0"
    exit 1
}

# Check if the correct number of arguments are provided
if [ "$#" -ne 0 ]; then
    usage
fi

# Set the bucket location to a fixed value
BUCKET_LOCATION="us-central1"

# Get the current project ID
PROJECT_ID=$(gcloud config get-value project)

# Check if project ID is retrieved
if [ -z "$PROJECT_ID" ]; then
    echo "No project ID set. Please set the project using 'gcloud config set project <project_id>'."
    exit 1
fi

# Authenticate with GCP
echo "Authenticating with GCP..."
gcloud auth login

# Set the GCP project
echo "Setting GCP project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable Firestore API
echo "Enabling Firestore API..."
gcloud services enable firestore.googleapis.com

# Create Firestore database
echo "Creating Firestore database..."
gcloud alpha firestore databases create --location=$BUCKET_LOCATION

# Create the bucket
echo "Creating the bucket..."
gsutil mb -l $BUCKET_LOCATION gs://$PROJECT_ID-my-bucket

# Copy the data from the source bucket to the new bucket
echo "Copying data to the new bucket..."
gsutil cp -r gs://sessions-master-database-bucket/2024-03-26T09:28:15_95256 gs://$PROJECT_ID-my-bucket

# Import data into Firestore
echo "Importing data into Firestore..."
gcloud firestore import gs://$PROJECT_ID-my-bucket/2024-03-26T09:28:15_95256

echo "All steps completed successfully."
