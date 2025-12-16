import json
import boto3
import uuid

# --- CONFIGURACIÓN ---
REGION = 'us-east-1'
API_ID = 'g87vsd43u3'
MIN_PLAYERS_FOR_GAME = 2 # Normal mode

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
matches_table = dynamodb.Table('GameMatches')

# Construimos la URL del API Gateway
endpoint_url = f'https://{API_ID}.execute-api.{REGION}.amazonaws.com/prod'
# Cliente para enviar mensajes WebSocket
gatewayapi = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)

# URL de la Cola SQS (Reemplazar con la tuya si cambia)
QUEUE_URL = f'https://sqs.{REGION}.amazonaws.com/420660210592/GameQueue'

def lambda_handler(event, context):
    """
    Esta función tiene DOS trabajos:
    1. 'Matchmaker': Busca jugadores en la cola SQS y crea partidas.
    2. 'Broadcaster' (Proxy): Recibe mensajes del GameLoop y los envía a los Websockets
       (Esto se usa para saltarse restricciones de VPC si fuera necesario).
    """

    # === MODO CARTERO (Broadcaster Bypass) ===
    if event.get('action') == 'broadcast':
        messages = event.get('messages', [])
        # print(f"Modo Cartero: Entregando {len(messages)} cartas...")
        for item in messages:
            try:
                gatewayapi.post_to_connection(ConnectionId=item['cid'], Data=item['data'])
            except Exception as e:
                # Si falla (jugador se fue), lo ignoramos para no parar el juego
                pass
        return {'statusCode': 200, 'body': 'Mensajes Entregados'}

    # === MODO MATCHMAKER (Normal) ===
    print("Matchmaker revisando la cola...")
    
    try:
        # 1. Leer de SQS
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL, 
            MaxNumberOfMessages=10, # Intentamos jalar hasta 10
            WaitTimeSeconds=1       # Long Polling breve
        )

        if 'Messages' not in response:
            print("La cola está vacía.")
            return {'status': 'Cola vacía'}

        messages = response['Messages']
        player_count = len(messages)
        print(f"Se encontraron {player_count} jugadores.")

        # 2. Verificar si hay suficientes
        if player_count >= MIN_PLAYERS_FOR_GAME:
            print("¡Suficientes jugadores! Creando partida...")
            
            # Extraer Connection IDs
            player_connection_ids = []
            for msg in messages:
                try:
                    body = json.loads(msg['Body'])
                    player_connection_ids.append(body['connectionId'])
                except:
                    print("Mensaje SQS mal formado o vacío, saltando...")

            # 3. Crear Partida en DynamoDB
            match_id = str(uuid.uuid4())
            matches_table.put_item(
                Item={
                    'matchId': match_id, 
                    'players': player_connection_ids,
                    'status': 'ACTIVE',
                    # 'gameState' se creará en el primer loop
                }
            )
            print(f"Partida {match_id} creada en DynamoDB con: {player_connection_ids}")

            # 4. Notificar a los Jugadores ("Match Found!")
            notification = json.dumps({'type': 'matchFound', 'matchId': match_id})
            for connection_id in player_connection_ids:
                try:
                    gatewayapi.post_to_connection(ConnectionId=connection_id, Data=notification)
                except Exception as e:
                    print(f"No se pudo notificar a {connection_id}: {e}")
            
            # 5. INVOCAR AL GAME LOOP (Start Engine)
            # Invocamos asíncronamente (Event) para que empiece a rodar
            print("Arrancando el Game Loop...")
            lambda_client.invoke(
                FunctionName='gameLoopHandler',
                InvocationType='Event',
                Payload=json.dumps({'matchId': match_id})
            )

            # 6. Borrar mensajes de SQS (Para que no vuelvan a entrar a otra partida)
            entries = [{'Id': msg['MessageId'], 'ReceiptHandle': msg['ReceiptHandle']} for msg in messages]
            if entries:
                sqs.delete_message_batch(QueueUrl=QUEUE_URL, Entries=entries)
            
            print("TODO LISTO. Match iniciado.")
            return {'status': 'Partida INICIADA'}
        
        else:
            print(f"Faltan jugadores. Tenemos {player_count}, necesitamos {MIN_PLAYERS_FOR_GAME}.")
            return {'status': 'Esperando más jugadores'}

    except Exception as e:
        print(f"ERROR GRAVE EN MATCHMAKER: {e}")
        raise e
