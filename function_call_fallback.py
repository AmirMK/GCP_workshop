
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


def function_call(project_id, location, text):
    
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
                                    "transition_feeling": {"type": "array", "description": "scene transtions type for vieiwer"},
                                    "transition_type": {"type": "string", "description": "The method used to switch from one scene to another like cuts, fades, dissolves, etc."},
                                    "summary": {"type": "string", "description": "summary of the scene"},
                                    "narrative_type": {"type": "array", "description": "The list of the role or significance of the scene in the storyline like pivotal, climatic, conflict, etc."}, 
                                    "dialogue_intensity": {"type": "string", "description": "The amount and intensity of dialogue in the scene like monologue, dialogue, narration, debate, etc."},
                                    "characters_type": {"type": "array", "description": "The types of characters involved in the scene transition like protagonist, antagonist, supporting, etc."}, 
                                    "scene_categories": {"type": "array", "description": "Classification of the scene before the change into the categories such as action, drama, comedy, etc."},
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

