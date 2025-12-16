import json
import boto3
import os

# Clientes AWS
sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')

# Configuración (Variables de Entorno preferiblemente, pero hardcoded para este demo)
REGION = 'us-east-1'
ACCOUNT_ID = '420660210592'
QUEUE_NAME = 'GameQueue'
QUEUE_URL = f'https://sqs.{REGION}.amazonaws.com/{ACCOUNT_ID}/{QUEUE_NAME}'
MATCHES_TABLE = 'GameMatches'

def lambda_handler(event, context):
    """
    Maneja eventos de WebSocket ($connect, $disconnect) y rutas custom (joinQueue, playerMove).
    """
    route_key = event.get('requestContext', {}).get('routeKey')
    connection_id = event.get('requestContext', {}).get('connectionId')
    
    print(f"Endpoint recibido: {route_key} | CID: {connection_id}")

    if route_key == '$connect':
        # Simplemente aceptamos la conexión
        return {'statusCode': 200, 'body': 'Connected'}

    elif route_key == '$disconnect':
        # Manejo de desconexión (opcional: quitar de cola, notificar partida, etc.)
        # Por ahora simple log
        print(f"Cliente desconectado: {connection_id}")
        return {'statusCode': 200, 'body': 'Disconnected'}

    elif route_key == 'joinQueue':
        # El jugador quiere jugar. Lo mandamos a SQS.
        try:
            msg_body = json.dumps({'connectionId': connection_id})
            sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=msg_body)
            print("Jugador enviado a SQS.")
            
            # (Opcional) Podríamos invocar al Matchmaker inmediatamente para chequear
            # boto3.client('lambda').invoke(FunctionName='gameMatchmaker', InvocationType='Event')
            
            return {'statusCode': 200, 'body': 'Joined Queue'}
        except Exception as e:
            print(f"Error SQS: {e}")
            return {'statusCode': 500, 'body': 'Error adding to queue'}

    elif route_key == 'playerMove':
        # El jugador presionó una tecla.
        try:
            body = json.loads(event.get('body', '{}'))
            match_id = body.get('matchId')
            direction = body.get('direction')
            
            if match_id and direction:
                # Escribimos el INPUT en una tabla de DynamoDB o lo pasamos...
                # Para nuestra arquitectura "Dynamo-Only", lo ideal sería guardar el input
                # en la columna 'gameState' o una columna 'inputs' de la tabla Matches.
                # Aquí haremos un update simple.
                
                table = dynamodb.Table(MATCHES_TABLE)
                
                # Actualizar el input específico de este jugador en la partida
                # Nota: Esto requiere que el GameLoop lea estos inputs
                # Usaremos un mapa inputs.#CID = DIR
                table.update_item(
                    Key={'matchId': match_id},
                    UpdateExpression=f"SET inputs.{connection_id} = :d",
                    ExpressionAttributeValues={':d': direction},
                    ReturnValues="NONE"
                )
                return {'statusCode': 200, 'body': 'Move Registered'}
                
        except Exception as e:
            print(f"Error registrando movimiento: {e}")
            return {'statusCode': 500, 'body': 'Move Error'}

    return {'statusCode': 404, 'body': 'Route not found'}
