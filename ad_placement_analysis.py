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

import function_call_back as fc
import gcp_data_handler as gdata


def prompt_builder():                
 
    prompt = '''

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

        Using this JSON schema:
            detected_scence_changes = {"timestamp": str,
                                        "reason": str,
                                        "summary": str,
                                        "transition_feeling": array,
                                        "transition_type": array,
                                        "narrative_type": array,
                                        "dialogue_intensity": str,
                                        "characters_type": array,
                                        "scene_categories": array,
                                        }
        Return a `list[detected_scence_changes]`
        

      
      '''      


    
    return  prompt


def generate_scene(project_id, location, video_file_url,prompt):
    
    generation_config = GenerationConfig(temperature=0)
    vertexai.init(project=project_id, location=location)
    model_id = "gemini-1.5-pro-001"  
           
    model = GenerativeModel(model_id,
                       generation_config={"response_mime_type": "application/json"})                  
    
    video_file = Part.from_uri(video_file_url, mime_type="video/mp4")
    contents = [video_file, prompt]

    try:
        response = model.generate_content(contents,generation_config=generation_config)
    except:
        print('generation not proceed...')
        response = {'text':None}

    return response



def extract_json_list(json_string):
    # Remove the surrounding ```json and ``` if present
    if json_string.startswith("```json"):
        json_string = json_string[len("```json"):].strip()
    if json_string.endswith("```"):
        json_string = json_string[:-len("```")].strip()
        
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


def post_processing(response, movie_name, bucket_name, destionation, project_id,location):
    json_list = extract_json_list(response.text)
    if json_list is not None and inspect_json_structure(json_list):
        df_respons = pd.DataFrame(json_list)
        return df_respons
    else:
        try:
            print(f'try function calling for {movie_name}...')
            json_ = fc.function_call(project_id,location,response.text)
            json_list = fc.get_function_args(json_)['scences']
            df_respons = pd.DataFrame(json_list)
            return df_respons
        except:
            return None

    
def main():
    project_id = "[project-id]"
    location = "us-central1"
    dataset_id = 'movie_processing'
    table_id = 'movie_output'
    destionation = 'movie_processing_output'
    origine = 'movie_processing_input'
    
    bucket_name = f"bucket-{project_id}-video-analysis"

    

    movies = gdata.get_files(project_id, dataset_id, table_id, bucket_name, input_=origine)
    print(f'fetching {len(movies)} videos to process...')
    
    for file in movies:    
        movie_name = file.rsplit('.', 1)[0]    
        file_extension = file.rsplit('.', 1)[1]
        if file_extension.lower() == 'mp4':
            video_file_url = f"gs://{bucket_name}/{origine}/{file}"
    
    
            scene_transition = prompt_builder()
            print(f'analysing video: {movie_name}...')
            response = generate_scene(project_id, location, video_file_url,scene_transition)
    
            gdata.upload_to_gcs(data = response.text , bucket_name = bucket_name, 
                          destination_blob_name =  f"{destionation}/{movie_name}.text", data_type = 'string')
            print(f'post processing for {movie_name}...')
            df_respons = post_processing(response, movie_name, bucket_name, destionation, project_id,location)
            
            if df_respons is not None:
                print(f'write to bigquery for {movie_name}...')
                gdata.write_to_bigquery(df_respons, file, dataset_id, project_id,table_id)
            else:
                print(f'no data frame generated for {movie_name}...')
        else:
            print(f'{file} is not video format')

if __name__ == "__main__":
    main()
