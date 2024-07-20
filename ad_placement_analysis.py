import sys
import os

import time
import json
import re


from google.cloud import storage

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
        
      
        reason: The reason why this is a scene change and why it is a good location for ad placement. the reaosn 
        shoudl be very specific. Summrize the story after and before the scene and the explain why 
        between these two scence is a good place for an ad.
        
        transition_type: The feeling that the transition make in viewiers like exictment, peace, fear, etc.

      Please provide the output in the form of list of json.
      '''      
    

    
    return  scene_transition


def generate_scene(PROJECT_ID, LOCATION, video_file_url,prompt):
    
    generation_config = GenerationConfig(temperature=0)
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    MODEL_ID = "gemini-1.5-pro-001"  
       
    
    model = GenerativeModel(MODEL_ID)                           
    
    video_file = Part.from_uri(video_file_url, mime_type="video/mp4")
    contents = [video_file, prompt]

    response = model.generate_content(contents,generation_config=generation_config)

    return response


def get_json(PROJECT_ID, LOCATION, text):
    
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        generation_config = GenerationConfig(temperature=0)
        MODEL_ID = "gemini-1.5-pro-001"
        model = GenerativeModel(MODEL_ID)
       
               
        get_movie_scene_properties = FunctionDeclaration(
            name="get_characters_information",
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
                                    "transition_type": {"type": "string", "description": "scene transtions type for vieiwer"},
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
    input_file_bases = set(f[:-4] for f in input_files if f.endswith('.mp4'))
    output_file_bases = set(f[:-4] for f in output_files if f.endswith('.csv'))
    missing_csv_files = input_file_bases - output_file_bases
    return [f"{file_base}.mp4" for file_base in missing_csv_files]

def get_files(bucket_name, input_, output_):
    input_files = list_files(bucket_name, input_)
    output_files = list_files(bucket_name, output_)

    missing_csv_files = compare_files(input_files, output_files)
    
    return missing_csv_files


# Function 1: Extract the list of JSON objects from the string
def extract_json_list(json_string):
    # Remove the surrounding ```json and ``` if present
    if json_string.startswith("```json"):
        json_string = json_string[len("```json"):].strip()
    if json_string.endswith("```"):
        json_string = json_string[:-len("```")].strip()
    
    # Preprocess to escape unescaped double quotes within strings
    def escape_quotes(match):
        # Match groups of text within double quotes and escape double quotes inside them
        return match.group(0).replace('"', '\\"')
    
    # Escape unescaped double quotes within the JSON string
    json_string = re.sub(r'(?<=: ")(.*?)(?=",)', lambda m: m.group(1).replace('"', '\\"'), json_string)

    try:
        json_list = json.loads(json_string)
        return json_list
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e}")
        return None

    

# Function 2: Inspect the structure of nested JSON objects
def inspect_json_structure(json_list):
    for item in json_list:
        if not all(key in item for key in ("timestamp", "reason", "transition_type")):
            return False
    return True

# Function 3: Convert the list of JSON objects into a DataFrame
def convert_to_dataframe(json_list):
    df = pd.DataFrame(json_list)
    return df


def post_processing(response, movie_name, bucket_name, destionation):
    json_list = extract_json_list(response.text)
    if json_list is not None and inspect_json_structure(json_list):
        df_respons = convert_to_dataframe(json_list)
        upload_to_gcs(data = df_respons, bucket_name = bucket_name
                      , destination_blob_name = f"{destionation}/{movie_name}.csv", data_type = 'csv')
    else:
        try:
            print(f'try function calling for {movie_name}...')
            json_list = get_function_args(json_)['scences']
            df_respons = convert_to_dataframe(json_list)
            upload_to_gcs(data = df_respons, bucket_name = bucket_name
                      , destination_blob_name = f"{destionation}/{movie_name}.csv", data_type = 'csv')
        except:
            pass

def main():
    PROJECT_ID = [project-id]
    LOCATION = "us-central1"


    bucket_name = f"bucket-{PROJECT_ID}-video-analysis"
    destionation = 'movie_processing_output'
    origine = 'movie_processing_input'

    movies = get_files(bucket_name, input_ = origine, output_ = destionation)

    for file in movies:    
        movie_name = file.rsplit('.', 1)[0]    
        video_file_url = f"gs://{bucket_name}/{origine}/{file}"


        scene_transition = prompt_builder()
        print(f'analysing video: {movie_name}...')
        response = generate_scene(PROJECT_ID, LOCATION, video_file_url,scene_transition)

        upload_to_gcs(data = response.text , bucket_name = bucket_name, 
                      destination_blob_name =  f"{destionation}/{movie_name}.text", data_type = 'string')
        print(f'post processing for {movie_name}...')
        post_processing(response, movie_name, bucket_name, destionation)


if __name__ == "__main__":
    main()
