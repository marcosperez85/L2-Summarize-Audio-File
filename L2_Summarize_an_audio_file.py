#!/usr/bin/env python
# coding: utf-8

# # Lesson 2: Summarize an audio file

# ### Import all needed packages
import pygame
import boto3
import uuid
import time
import json
import logging
from botocore.exceptions import ClientError
from jinja2 import Template

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ### Let's start with transcribing an audio file

# El siguiente código es para poder reproducir un audio en Python dado que la librería IPython es propia del entorno de Jupyter
# Por ese motivo es que se tiene que importar la librería pygame si sólo se trabaja desde VS Code.
pygame.mixer.init()
pygame.mixer.music.load("dialog.mp3")
# pygame.mixer.music.play()

# input("\nPresiona Enter para detener la reproducción...")
# pygame.mixer.music.stop()

# Especifico mi sesión de para el usuario del IAM Identity Center (SSO)
session = boto3.Session(profile_name="AdministratorAccess-376129873205")

# Crear cliente de S3 en la región ingresada sino toma us-east-1 por default
s3_client = session.client('s3', region_name = "us-east-1")

# Creo un objeto s3 para para poder trabajar sobre el mismo. No era parte del tutorial pero lo agergué yo para algunas
# validaciones dentro de VS Code
recurso_s3 = session.resource('s3')

# Guardo en una variable el nombre del bucket
# En el tutorial tienen guardado el nombre del bucket en una variable de entorno de Jupyter. En este caso no voy a hacer eso
# por lo que no es necesario importar la librería "os" ni tampoco traerme el nombre del bucket desde una variable de entorno.
# Entonces, dado que lo dejo "hardcodeado" agrego un condicional en caso de que un día borre dicho bucket en AWS.

def buscarSiExisteBucket(bucket_name):
    # Obtener la lista de nombre de buckets
    # s3.buckets.all() devuelve un iterador con todos los objetos de tipo Bucket en la cuenta de AWS.
    # Luego se recorre cada objeto "bucket" en s3.buckets.all(), obteniendo su nombre con bucket.name
    # Esto es un "list comprehension" que es una forma abreviada de crear una lista 
    buckets = [bucket.name for bucket in recurso_s3.buckets.all()]
    
    # La instrucción anterior devuelve una lista de objetos, no strings. Además no se puede evaluar son strings,
    # sólo se puede evaluar con índices. Así que tengo que usar la sintaxis "elem in list" o "elem not in list"
    if bucket_name not in buckets:
        logging.info(f"\n\nEl bucket '{bucket_name}' no pudo encontrarse y va a ser creado en us-east-1")
        return crearBucket(bucket_name)

    else:
        logging.info(f"\n\nEl bucket '{bucket_name}' fue encontrado en us-east-1 y no hace falta crearlo")
        return True

def crearBucket(nombreDeBucket):
    #Crear bucket en region us-east-1
    s3_client.create_bucket(Bucket = nombreDeBucket)
    logging.info(f"\n\nEl bucket '{nombreDeBucket}' fue creado con éxito en la región us-east-1'")
    return True

bucket_name = 'bucket-l2-summarize-audio-file'
buscarSiExisteBucket(bucket_name)

"""
file_name = 'dialog.mp3'
s3_client.upload_file(file_name, bucket_name, file_name)
transcribe_client = boto3.client('transcribe', region_name='us-east-2')
job_name = 'transcription-job-' + str(uuid.uuid4())
job_name

response = transcribe_client.start_transcription_job(
    TranscriptionJobName=job_name,
    Media={'MediaFileUri': f's3://{bucket_name}/{file_name}'},
    MediaFormat='mp3',
    LanguageCode='en-US',
    OutputBucketName=bucket_name,
    Settings={
        'ShowSpeakerLabels': True,
        'MaxSpeakerLabels': 2
    }
)

while True:
    status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
    if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
        break
    time.sleep(2)

print(status['TranscriptionJob']['TranscriptionJobStatus'])

if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
    
    # Load the transcript from S3.
    transcript_key = f"{job_name}.json"
    transcript_obj = s3_client.get_object(Bucket=bucket_name, Key=transcript_key)
    transcript_text = transcript_obj['Body'].read().decode('utf-8')
    transcript_json = json.loads(transcript_text)
    
    output_text = ""
    current_speaker = None
    
    items = transcript_json['results']['items']
    
    for item in items:
        
        speaker_label = item.get('speaker_label', None)
        content = item['alternatives'][0]['content']
        
        # Start the line with the speaker label:
        if speaker_label is not None and speaker_label != current_speaker:
            current_speaker = speaker_label
            output_text += f"\n{current_speaker}: "
            
        # Add the speech content:
        if item['type'] == 'punctuation':
            output_text = output_text.rstrip()
            
        output_text += f"{content} "
        
    # Save the transcript to a text file
    with open(f'{job_name}.txt', 'w') as f:
        f.write(output_text)


# ### Now, let's use an LLM

bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')

with open(f'{job_name}.txt', "r") as file:
    transcript = file.read()

get_ipython().run_cell_magic('writefile', 'prompt_template.txt', 'I need to summarize a conversation. The transcript of the \nconversation is between the <data> XML like tags.\n\n<data>\n{{transcript}}\n</data>\n\nThe summary must contain a one word sentiment analysis, and \na list of issues, problems or causes of friction\nduring the conversation. The output must be provided in \nJSON format shown in the following example. \n\nExample output:\n{\n    "sentiment": <sentiment>,\n    "issues": [\n        {\n            "topic": <topic>,\n            "summary": <issue_summary>,\n        }\n    ]\n}\n\nWrite the JSON output and nothing more.\n\nHere is the JSON output:\n')

with open('prompt_template.txt', "r") as file:
    template_string = file.read()

data = {
    'transcript' : transcript
}

template = Template(template_string)
prompt = template.render(data)
print(prompt)

kwargs = {
    "modelId": "amazon.titan-text-express-v1",
    "contentType": "application/json",
    "accept": "*/*",
    "body": json.dumps(
        {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 512,
                "temperature": 0,
                "topP": 0.9
            }
        }
    )
}

response = bedrock_runtime.invoke_model(**kwargs)
response_body = json.loads(response.get('body').read())
generation = response_body['results'][0]['outputText']
print(generation)
"""