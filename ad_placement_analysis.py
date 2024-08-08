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

from proto.marshal.collections import repeated
from proto.marshal.collections import maps


import vertexai

from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel,
    HarmBlockThreshold,
    HarmCategory,
    Part,
    Content,
    FunctionDeclaration,
    GenerationResponse,
    Tool,
)



def prompt_builder():                
 
    scene_transition = '''

       I have a video that I need you to analyze for ad placement by detecting scene changes, 
       also known as shot boundaries. I need to identify the 10 best scene changes across the 
       entire movie, which are the best potential points for ad placement as they minimize 
       interruptions for viewers. These scene changes should be selected from all parts of the movie: 
       the beginning, middle, and the very end. Make sure you distribute the selected scenes evenly across 
       the entire movie.
       For each of these scene changes, please provide:

        timestamp: The exact timestamps indicating where the scene change occurs. Make sure that the timestamp of scenes are matched those in the original movie,
        reflecting its position accurately. The timestamps must exactly match those in the original movie.
        
        reason: The reason why this is a scene change and why it is a good location for ad placement. the reason 
        should be very specific. Summarize the story after and before the scene and the explain why 
        between these two scene is a good place for an ad.
        
        summary: A brief summary of the scene before the change.
        
        transition_feeling: The list of the feelings that the transition makes in viewers like excitement, peace, fear, etc.
        
        transition_type: The method used to switch from one scene to another like cuts, fades, dissolves, etc.
        
        narrative_type: The list of the role or significance of the scene in the storyline like pivotal, climatic, conflict, etc.
        
        dialogue_intensity: The amount and intensity of dialogue in the scene like monologue, dialogue, narration, debate, etc.

        characters_type: The types of characters involved in the scene transition like protagonist, antagonist, supporting, etc.
        
        scene_categories:  Classification of the scene before the change into the categories such as action, drama, comedy, etc.

       Please provide the output in the form of a list of json.

      
      '''      

    

    
    return  scene_transition


def generate_scene(project_id, location, video_file_url,prompt):
    
    generation_config = GenerationConfig(temperature=0)
    vertexai.init(project=project_id, location=location)
    model_id = "gemini-1.5-pro-001"  
       
    
    model = GenerativeModel(model_id)                           
    
    video_file = Part.from_uri(video_file_url, mime_type="video/mp4")
    contents = [video_file, prompt]

    response = model.generate_content(contents,generation_config=generation_config)

    return response


def get_json(project_id, location, text):
    
        vertexai.init(project=project_id, location=location)
        generation_config = GenerationConfig(temperature=0)
        model_id = "gemini-1.5-pro-001"
        model = GenerativeModel(model_id)
       
               
        get_movie_scene_properties = FunctionDeclaration(
            name="get_scene_information",
            description="Get the scene information",
            parameters={
                "type": "object",
                "properties": {
                     "scences":{
                     "type": "array",
                      "description": "A list of scence in the movie",
                        "items": {
                                "description": "scences attributes",
                                "type": "object",
                                "properties": {
                                    "timestamp": {"type": "string", "description": "scene timestamp"},
                                    "reason": {"type": "string", "description": "why the scence is a scence change"},                                    
                                    "transition_feeling": {"type": "array", "description": "scene transtions type for vieiwer"},#
                                    "transition_type": {"type": "string", "description": "The method used to switch from one scene to another like cuts, fades, dissolves, etc."},
                                    "summary": {"type": "string", "description": "summary of the scene"},
                                    "narrative_type": {"type": "array", "description": "The list of the role or significance of the scene in the storyline like pivotal, climatic, conflict, etc."}, #
                                    "dialogue_intensity": {"type": "string", "description": "The amount and intensity of dialogue in the scene like monologue, dialogue, narration, debate, etc."},
                                    "characters_type": {"type": "array", "description": "The types of characters involved in the scene transition like protagonist, antagonist, supporting, etc."}, #
                                    "scene_categories": {"type": "array", "description": "Classification of the scene before the change into the categories such as action, drama, comedy, etc."},#
                                    },
                            
                                }
                        }

                    },
            
                },
            )

        
        geocoding_tool = Tool(
                function_declarations=[get_movie_scene_properties],
            )
       
        response_json = model.generate_content(
            text,
            tools=[geocoding_tool],generation_config=generation_config
                )

        
        
        return response_json

def recurse_proto_repeated_composite(repeated_object):
    repeated_list = []
    for item in repeated_object:
        if isinstance(item, repeated.RepeatedComposite):
            item = recurse_proto_repeated_composite(item)
            repeated_list.append(item)
        elif isinstance(item, maps.MapComposite):
            item = recurse_proto_marshal_to_dict(item)
            repeated_list.append(item)
        else:
            repeated_list.append(item)

    return repeated_list

def recurse_proto_marshal_to_dict(marshal_object):
    new_dict = {}
    for k, v in marshal_object.items():
        if not v:
            continue
        elif isinstance(v, maps.MapComposite):
            v = recurse_proto_marshal_to_dict(v)
        elif isinstance(v, repeated.RepeatedComposite):
            v = recurse_proto_repeated_composite(v)
        new_dict[k] = v

    return new_dict

def get_function_args(response: GenerationResponse) -> dict:
    return recurse_proto_marshal_to_dict(
        response.candidates[0].content.parts[0].function_call.args
    )


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



def extract_json_list(json_string):
    # Remove the surrounding ```json and ``` if present
    if json_string.startswith("```json"):
        json_string = json_string[len("```json"):].strip()
    if json_string.endswith("```"):
        json_string = json_string[:-len("```")].strip()
    
    # Preprocess to escape unescaped double quotes within strings
    def escape_quotes(match):
        # Match groups of text within double quotes and escape double quotes inside them
        return '"' + match.group(1).replace('"', '\\"') + '"'
    
    # Escape unescaped double quotes within the JSON string
    json_string = re.sub(r'(?<=:\s)"([^"]*?)"(?=,|})', escape_quotes, json_string)

    try:
        json_list = json.loads(json_string)
        return json_list
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e}")
        return None

    

def inspect_json_structure(json_list):
    required_keys = {"timestamp", "reason", "transition_type", 'summary','transition_feeling','transition_type','narrative_type','dialogue_intensity','characters_type','scene_categories'}
    
    
     
    
    for item in json_list:
        item_keys = set(item.keys())
        
        if item_keys != required_keys:
            return False
    return True


# Function 3: Convert the list of JSON objects into a DataFrame
def convert_to_dataframe(json_list):
    df = pd.DataFrame(json_list)
    return df


def post_processing(response, movie_name, bucket_name, destionation, project_id,location):
    json_list = extract_json_list(response.text)
    if json_list is not None and inspect_json_structure(json_list):
        df_respons = convert_to_dataframe(json_list)
        #upload_to_gcs(data = df_respons, bucket_name = bucket_name
        #              , destination_blob_name = f"{destionation}/{movie_name}.csv", data_type = 'csv')
        return df_respons
    else:
        try:
            print(f'try function calling for {movie_name}...')
            json_ = get_json(project_id,location,response.text)
            json_list = get_function_args(json_)['scences']
            df_respons = convert_to_dataframe(json_list)
            #upload_to_gcs(data = df_respons, bucket_name = bucket_name
            #          , destination_blob_name = f"{destionation}/{movie_name}.csv", data_type = 'csv')
            return df_respons
        except:
            return None

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

def create_dataset_if_not_exists(dataset_id, project_id):
    client = bigquery.Client()
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
    client = bigquery.Client()
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

    
def main():
    project_id = "lab-project-426319"
    location = "us-central1"
    dataset_id = 'movie_processing'
    table_id = 'movie_output'
    destionation = 'movie_processing_output'
    origine = 'movie_processing_input'

    bucket_name = 'genai-test-2'
    #bucket_name = f"bucket-{project_id}-video-analysis"

    

    movies = get_files(project_id, dataset_id, table_id, bucket_name, input_=origine)
    print(f'fetching {len(movies)} videos to process...')
    
    for file in movies:    
        movie_name = file.rsplit('.', 1)[0]    
        video_file_url = f"gs://{bucket_name}/{origine}/{file}"


        scene_transition = prompt_builder()
        print(f'analysing video: {movie_name}...')
        response = generate_scene(project_id, location, video_file_url,scene_transition)

        upload_to_gcs(data = response.text , bucket_name = bucket_name, 
                      destination_blob_name =  f"{destionation}/{movie_name}.text", data_type = 'string')
        print(f'post processing for {movie_name}...')
        df_respons = post_processing(response, movie_name, bucket_name, destionation, project_id,location)
        
        if df_respons is not None:
            print(f'write to bigquery for {movie_name}...')
            write_to_bigquery(df_respons, file, dataset_id, project_id,table_id)
        else:
            print(f'no data frame generated for {movie_name}...')

if __name__ == "__main__":
    main()
