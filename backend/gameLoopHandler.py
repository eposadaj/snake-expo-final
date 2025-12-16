import json
import boto3
import time
import random

# --- CONFIGURACIÓN ---
REGION = 'us-east-1'
API_ID = 'g87vsd43u3'
GRID_SIZE = 40 # 40x40 grid (800px / 20)

# Inicialización
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
table = dynamodb.Table('GameMatches')

endpoint_url = f'https://{API_ID}.execute-api.{REGION}.amazonaws.com/prod'
gatewayapi = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)

def lambda_handler(event, context):
    try:
        match_id = event.get('matchId')
        print(f"GameTick processing for Match: {match_id}")
        
        # 1. Recuperar Estado (Desde DynamoDB)
        resp = table.get_item(Key={'matchId': match_id})
        item = resp.get('Item', {})
        
        if not item:
            print("Match no encontrado en DB, abortando loop.")
            return
            
        # Si no hay estado guardado, lo inicializamos
        if 'gameState' not in item:
            game_state = init_game_state(item.get('players', []))
        else:
            # DynamoDB puede guardar JSON como string
            game_state = json.loads(item['gameState'])
            
        # Leer Inputs (Guardados en item['inputs'] por el ConnectionHandler)
        player_inputs = item.get('inputs', {})

        # 2. Lógica del Juego (Movimiento)
        update_game_state(game_state, match_id, player_inputs)

        # 3. Guardar Estado (En DynamoDB)
        # Limpiamos inputs procesados (opcional, o simplemente sobrescribimos estado)
        # En este modelo simple, no borramos inputs, solo leemos el último.
        table.update_item(
            Key={'matchId': match_id},
            UpdateExpression="set gameState = :s",
            ExpressionAttributeValues={':s': json.dumps(game_state)}
        )
        
        # 4. BROADCAST DIRECTO (Sin VPC)
        msg_content = json.dumps({'type': 'gameState', 'state': game_state})
        
        active_players = False
        for pid, p in game_state['players'].items():
            if p['alive']:
                 active_players = True
                 try:
                    gatewayapi.post_to_connection(ConnectionId=pid, Data=msg_content)
                 except Exception as e:
                     print(f"Error enviando frame a {pid} (posible desconexión): {e}")
                     # Si es GoneException, marcar como muerto en prox tick
                     # p['alive'] = False 

        # 5. Recursión
        # Ajustar velocidad. AWS Lambda cobra por 1ms.
        # Dormimos un poco para no spammear DynamoDB y mantener ~5 FPS
        time.sleep(0.15) 
        
        if active_players:
            # Auto-inovación para el siguiente frame
            lambda_client.invoke(FunctionName=context.function_name, InvocationType='Event', Payload=json.dumps(event))
        else:
            print("Todos muertos o desconectados. Game Over.")
            # table.delete_item(Key={'matchId': match_id}) # Limpieza

    except Exception as e:
        print(f"ERROR CRÍTICO EN GAME LOOP: {e}")
        # Importante: Si falla, el loop muere.
        # En producción querríamos reintentar o loguear mejor.
        raise e

    return {'statusCode': 200, 'body': 'Tick OK'}

def init_game_state(players):
    state = {'players': {}, 'food': {'x': random.randint(0, GRID_SIZE-1), 'y': random.randint(0, GRID_SIZE-1)}, 'width': GRID_SIZE, 'height': GRID_SIZE}
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f'] # Rojo, Azul, Verde, Amarillo
    
    for i, pid in enumerate(players):
        state['players'][pid] = {
            'id': pid, 'body': [{'x': 10 + (i*5), 'y': 10 + (i*5)}], 
            'dir': 'RIGHT', 'color': colors[i%4], 'score': 0, 'alive': True
        }
    print(f"Estado inicializado para {len(players)} jugadores")
    return state

def update_game_state(state, match_id, inputs):
    # Lógica de movimiento
    for pid, p in state['players'].items():
        if not p['alive']: continue
        
        # Aplicar Input si existe
        if pid in inputs:
            new_dir = inputs[pid]
            # Validación simple anti-reversa
            opposites = {'UP':'DOWN', 'DOWN':'UP', 'LEFT':'RIGHT', 'RIGHT':'LEFT'}
            if opposites.get(new_dir) != p['dir']:
                p['dir'] = new_dir
            
        # Movemos la cabeza
        head = p['body'][0]
        new_head = {'x': head['x'], 'y': head['y']}
        
        if p['dir'] == 'UP': new_head['y'] -= 1
        elif p['dir'] == 'DOWN': new_head['y'] += 1
        elif p['dir'] == 'LEFT': new_head['x'] -= 1
        elif p['dir'] == 'RIGHT': new_head['x'] += 1
        
        # Paredes (Muerte)
        if new_head['x'] < 0 or new_head['x'] >= state['width'] or new_head['y'] < 0 or new_head['y'] >= state['height']:
            p['alive'] = False
            continue
            
        # Comida
        food = state['food']
        # Colisión simple hitbox
        if new_head['x'] == food['x'] and new_head['y'] == food['y']:
            p['score'] += 10
            p['body'].insert(0, new_head) # Crece
            state['food'] = {'x': random.randint(0, state['width']-1), 'y': random.randint(0, state['height']-1)}
        else:
            p['body'].insert(0, new_head)
            p['body'].pop() # Se mueve (borra cola)
