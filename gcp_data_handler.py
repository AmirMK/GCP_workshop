import sys
import os

import time
from datetime import datetime, timedelta
import json
import re


from google.cloud import storage
from google.cloud import bigquery

import pandas as pd
import datetime


def upload_to_gcs(data, bucket_name, destination_blob_name, data_type):
    """
    Uploads data to Google Cloud Storage.
    
    Parameters:
    data (pd.DataFrame or str): Data to be uploaded.
    bucket_name (str): Name of the GCS bucket.
    destination_blob_name (str): Destination path within the GCS bucket.
    data_type (str): Type of data ('csv' for DataFrame, 'string' for text data).
    """
    # Create a GCS client
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    if data_type == 'csv':
        # Convert DataFrame to CSV
        csv_data = data.to_csv(index=False)
        # Upload the data as CSV
        blob.upload_from_string(csv_data, content_type='text/csv')
        print(f"DataFrame saved as CSV to gs://{bucket_name}/{destination_blob_name}")
    
    elif data_type == 'string':
        # Upload the string data
        blob.upload_from_string(data, content_type='text/plain')
        print(f"Text data uploaded to gs://{bucket_name}/{destination_blob_name}")
    
    else:
        raise ValueError("Unsupported data_type. Use 'csv' for DataFrame or 'string' for text data.")


        
def create_dataset_if_not_exists(dataset_id, project_id):
    client = bigquery.Client(project=project_id)
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset {dataset_id} already exists")
    except:
        # Create the dataset if it does not exist
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"  # Specify the location as needed
        client.create_dataset(dataset)
        print(f"Created dataset {dataset_id}")

        
def write_to_bigquery(df, file_name, dataset_id, project_id, table_id):
    client = bigquery.Client(project=project_id)
    # Check if the dataset exists and create it if not
    create_dataset_if_not_exists(dataset_id, project_id)
    
    table_id = f"{project_id}.{dataset_id}.{table_id}"
    
    # Add 'movie' column to the dataframe
    df['movie'] = file_name
    
    # Convert lists within the dataframe to JSON strings
    df = convert_lists_to_json_strings(df)
    
    # Convert timestamp columns
    df = convert_timestamp_columns(df)
    
    # Define the schema based on the dataframe columns
    schema = []
    for column in df.columns:
        if column == 'movie':
            schema.append(bigquery.SchemaField(column, 'STRING'))
        elif column in ['timestamp', 'start_time', 'end_time']:
            schema.append(bigquery.SchemaField(column, 'TIMESTAMP'))
        elif pd.api.types.is_numeric_dtype(df[column]):
            schema.append(bigquery.SchemaField(column, 'FLOAT'))
        elif pd.api.types.is_datetime64_any_dtype(df[column]):
            schema.append(bigquery.SchemaField(column, 'TIMESTAMP'))
        else:
            schema.append(bigquery.SchemaField(column, 'STRING'))  # Adjust data types as necessary
    
    # Define table options
    table = bigquery.Table(table_id, schema=schema)
    
    # Check if the table exists
    try:
        client.get_table(table_id)
    except:
        # Create the table if it does not exist
        table = client.create_table(table)
        print(f"Created table {table_id}")

    # Write the dataframe to the BigQuery table
    job = client.load_table_from_dataframe(df, table_id)
    job.result()  # Wait for the job to complete
    
    print(f"Data has been written to {table_id}")

    
def list_files(bucket_name, prefix):
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    return [blob.name[len(prefix):].lstrip('/') for blob in blobs]



def compare_files(input_files, output_files):
    input_file_bases = set(input_files) #f[:-4] for f in input_files if f.endswith('.mp4'))
    output_file_bases = set(output_files) #f[:-4] for f in output_files if f.endswith('.csv'))
    missing_csv_files = input_file_bases - output_file_bases
    return [f"{file_base}" for file_base in missing_csv_files]


def get_distinct_movies(project_id, dataset_id, table_id):
    client = bigquery.Client(project=project_id)
    
    try:
        # Check if dataset exists
        dataset_ref = client.dataset(dataset_id)
        client.get_dataset(dataset_ref)  # Will raise NotFound if dataset does not exist
        
        # Check if table exists
        table_ref = dataset_ref.table(table_id)
        client.get_table(table_ref)  # Will raise NotFound if table does not exist

        # If dataset and table exist, query distinct values of 'movie' column
        query = f"""
        SELECT DISTINCT movie
        FROM `{project_id}.{dataset_id}.{table_id}`
        """
        query_job = client.query(query)
        results = query_job.result()
        
        # Extract distinct movie values
        movies = [row.movie for row in results]
        return movies
    
    except:
        return []
    

def get_files(project_id, dataset_id, table_id, bucket_name, input_):
    input_files = list_files(bucket_name, input_)
    output_files = get_distinct_movies(project_id, dataset_id, table_id)

    missing_csv_files = compare_files(input_files, output_files)
    
    return missing_csv_files


def convert_lists_to_json_strings(df):
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, list)).any():
            df[col] = df[col].apply(json.dumps)
    return df


def convert_timestamp_columns(df):
    def parse_time(x):
        if isinstance(x, str):
            try:
                parsed_time = datetime.datetime.strptime(x, '%M:%S')
                return parsed_time
            except ValueError:
                return pd.NaT
        return x
    
    lag = 5
    df['timestamp'] = df['timestamp'].apply(parse_time)
    df['start_time'] = df['timestamp'].apply(lambda x: x - timedelta(seconds=lag) if pd.notna(x) else pd.NaT)
    df['end_time'] = df['timestamp'].apply(lambda x: x + timedelta(seconds=lag) if pd.notna(x) else pd.NaT)
    
    
    return df

