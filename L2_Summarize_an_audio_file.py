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
import os
from botocore.exceptions import ClientError
from jinja2 import Template

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ### Let's start with transcribing an audio file

# El siguiente código es para poder reproducir un audio en Python dado que la librería IPython es propia del entorno de Jupyter
# Por ese motivo es que se tiene que importar la librería pygame si sólo se trabaja desde VS Code.
if os.path.exists("dialog.mp3"):
    pygame.mixer.init()
    pygame.mixer.music.load("dialog.mp3")
    #pygame.mixer.music.play()
else:
    logging.error("El archivo 'dialog.mp3' no se encontró.")

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
bucket_name = 'bucket-para-archivos-mp3-20250202'

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

# Llamo a la función de verificación de existencia del bucket
buscarSiExisteBucket(bucket_name)

# ===============================================
# Sección para subir archivos de audio

file_name = 'dialog.mp3'

# Recordar que un archivo dentro de un bucket recibe el nombre de "objeto". Para simplificar el código vamos a hacer
# que el nombre del objeto (último parámetro) sea el mismo que el nombre de la función.

def buscarSiExisteObjeto(file_name, bucket_name):

    # Obtener el objeto Bucket de nuestro bucket específico.
    objetoBucket = recurso_s3.Bucket(bucket_name)

    # Crear una lista usando el list comprehension
    listaDeObjetos = [obj.key for obj in objetoBucket.objects.all()]    
    
    if file_name not in listaDeObjetos:
        return subirArchivo(file_name, bucket_name)
    else:
        logging.info("\nEl archivo ya existía en el bucket")
        return False
    

def subirArchivo(nombreDeArchivo, nombreDelBucket):
    try:
        s3_client.upload_file(nombreDeArchivo, nombreDelBucket, nombreDeArchivo)
        logging.info(f"\nEl archivo '{nombreDeArchivo} fue subido con éxito al bucket '{nombreDelBucket}")

    except ClientError as err:
        logging.info(f"\nNo se pudo subir el archivo debido al error:\n\n{err}")        
        return False
    return True

buscarSiExisteObjeto(file_name, bucket_name)


# ===============================================
# Sección para transcribir un archivo de audio alojado en nuestro bucket S3

# Crear cliente del servicio "Transcribe" en la región ingresada sino toma us-east-1 por default
transcribe_client = session.client('transcribe', region_name='us-east-1')

# Dado que el servicio de transcripción necesita que se le pase como parámetro un  nombre de job que sea único,
# usamos la función "uuid" (Universal Unique ID) que sirve para generar strings únicos de letras y números.
# Tiene cinco métodos de generación pero en el tutorial indicaron de usar sólo el 4.
job_name = 'transcription-job-' + str(uuid.uuid4())

# El Transcribe necesita que se le pase el job name al igual que nombre del archivo el cual tiene que procesar.
# También hay que pasarle el formato del archvo y para una mejor performance en la transcripción, conviene ayudarla indicando
# cuál es el idioma del audio, cuánta es la cantidad máxima de personas hablando y que la transcripción segregue el texto de
# una persona respecto de la otra.
# Finalmente el resultado de la transcripción lo almacena en un bucket S3 (que en este caso es el mismo que el del MP3)
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


# ===============================================
# Sección para verificar el progreso de la transcripción

# Este bucle se repite cada dos segundos siempre y cuando el status de la transcripción NO SEA COMPLETED o FAILED.
# Se ser alguno de esos casos, sale del bucle y continúa con el resto del código.
while True:
    status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
    if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
        break
    time.sleep(2)
    print(f"Generando transcripción, por favor espere.")
    

# Mostrar status final de la transcripción. Dado que el bucle anterior sólo se terminaba con COMPLETED o FAILED, 
# el status al mostrar en pantalla va a ser alguno de esos dos.
print(f"\nEl estado de la transcripción es: {status['TranscriptionJob']['TranscriptionJobStatus']}")


# ===============================================
# Sección para formatear la transcripción y mejorar el formato.

if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
    
    # Load the transcript from S3.
    transcript_key = f"{job_name}.json"
    transcript_obj = s3_client.get_object(Bucket=bucket_name, Key=transcript_key)
    transcript_text = transcript_obj['Body'].read().decode('utf-8')
    transcript_json = json.loads(transcript_text)

    # Explicación de lo anterior:
    # 1) Guardo el nombre del archivo de la transcripción en una variable. El nombre del archivo va a ser el nombre del job.
    # 2) Accedo al archivo dentro del bucket. Para eso paso como parámetro el nombre del bucket y del archivo
    #    (el cual es el transcription key)
    # 3) Leemos el body del archivo sin guardarlo en disco y le cambiamos el formato a UTF-8.
    #    Esto nos va a dar un texto en formato JSON pero no deja de ser un texto.
    # 4) Usamos json.loads para parsar un archivo JSSON en un objet diccionario de Python

    # Este objeto transcript_json va a contener toda la transcripción pero sin diferenciar a cada speaker.
    # Por este motivo el siguiente código hace una iteración en donde se mejora el formato para lograr que quede con
    # la estructura: "speaker: contenido"
    
    # Inicializar variables
    output_text = ""
    current_speaker = None   

    # El instructor del curso mostró el contenido de "transcript_json" para saber que tenía que bucar dentro de los keys
    # "results" y luego dentro de "items"
    items = transcript_json['results']['items']
    
    for item in items:
        
        speaker_label = item.get('speaker_label', None)
        content = item['alternatives'][0]['content']
        
        # Start the line with the speaker label:
        if speaker_label is not None and speaker_label != current_speaker:
            current_speaker = speaker_label
            output_text += f"\n{current_speaker}: "
            
        # Add the speech content:
        # Esto elimina los espacios (trailing spaces) al final de cada oración. No era muy necesario esto.
        if item['type'] == 'punctuation':
            output_text = output_text.rstrip()

        # Concatenar el nombre del speaker con el contenido propiamente dicho    
        output_text += f"{content} "
        
    # Guardar el resultado de la transcripción y formateo en un archivo de texto localmente (no en S3)
        with open(f'{job_name}.txt', 'w', encoding='utf-8') as f:
            f.write(output_text)
            print(f"\nSe ha creado con éxito el archivo: '{job_name}.txt' en la carpeta local.")


# ===============================================
# Sección para crear el resumen en base a la transcripción.

bedrock_runtime = session.client('bedrock-runtime', region_name='us-east-1')


# Abrir el archivo de texto local con la transcripción que se realizó antes
with open(f'{job_name}.txt', "r") as file:
    transcript = file.read()

# El instructor explica que en el módulo anterior (L1) habíamos usado un string para generar un prompt
# También es factible concatenación de strings y F-String para agregar variables.
# Sin embargo para un entorno de producción como es este caso donde tenemos una arquitectura Serverless, es más conveniente
# o más manejable, usar un template en un archivo separado. En este caso vamos a usar Jinja que es la librería de templates.
# Al usar un template en un archivo separado, se puede realizar un control de versiones y separar el código del template del
# código de la aplicación. Esto permite intercambiar prompts en vivo mientras la aplicación está en producción.

# En el tutorial original se usa una instrucción propia del notebook de Jupyter para crear un archivo con el prompt
# Sin embargo acá en Python no tenemos esa misma instrucción de IPython por lo que el TXT del prompt ya lo dejé localmente.
# y se llama "prompt_template.txt"

# Leemos el archivo de texto del prompt y lo guardamos en una variable.
with open('prompt_template.txt', "r") as file:
    template_string = file.read()

# Si miramos el prompt, sólo nos interesa completar un tag de XML llamado "data" el cual va a contener el "transcript"
# Luego a ese key de transcript le cargamos la variable "transcript" obtenida anteriormente al leer el prompt_template.txt
data = {
    'transcript' : transcript
}

# Llamamos al objeto Template que nos habíamos traido de la librería Jinja y le cargamos el contenido
# de la variable template_string. Para más comodidad ese objeto se lo asignamos a una variable llamada "template" también.
template = Template(template_string)

# Renderizamos todo y lo almacenamos en una variable llamada "prompt". 
# Todo esto es para no tener que crear un prompt manualmente donde le hagamos un copy/paste de la transcripción.
# Una vez más, se pudo haber hecho con concatenación de strings y con el uso de F-String pero de esta forma podemos
# editar el archivo de prompt en vivo y llevar un control de versiones.
prompt = template.render(data)

# Todo lo que sigue ahora es igual a lo que habíamos hecho en el módulo L1.
kwargs = {
    "modelId": "amazon.titan-text-lite-v1",
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
