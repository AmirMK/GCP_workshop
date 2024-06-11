#!/bin/bash

# Check if the correct number of arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <project_id> <bucket_location>"
    exit 1
fi

# Assign the arguments to variables
PROJECT_ID=$1
BUCKET_LOCATION=$2

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
