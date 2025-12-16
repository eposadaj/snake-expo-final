# AWS Serverless Snake: Arquitectura Multijugador en Tiempo Real

![AWS](https://img.shields.io/badge/AWS-Serverless-orange?style=for-the-badge&logo=amazon-aws)
![Python](https://img.shields.io/badge/Backend-Python-blue?style=for-the-badge&logo=python)
![DynamoDB](https://img.shields.io/badge/Database-DynamoDB-4053D6?style=for-the-badge&logo=amazon-dynamodb)
![Status](https://img.shields.io/badge/Status-Operational-green?style=for-the-badge)

## Descripción General del Proyecto

**AWS Serverless Snake** es un videojuego multijugador masivo en tiempo real (MMO-lite) diseñado e implementado completamente sobre una arquitectura Serverless.

A diferencia de los juegos multijugador tradicionales que dependen de flotas dedicadas de instancias EC2 ejecutándose 24/7, este proyecto demuestra un enfoque **Orientado a Eventos (Event-Driven)**. La infraestructura aprovisiona recursos dinámicamente solo cuando hay juego activo, resultando en un modelo de costos de "Escalado a Cero" (Scale-to-Zero) con alta eficiencia operativa.

### Características Principales

*   **Sincronización en Tiempo Real:** Entorno competitivo para dos jugadores con sincronización de latencia sub-segundo.
*   **Emparejamiento Dinámico (Matchmaking):** Sistema de lobby automatizado que utiliza colas asíncronas para agrupar jugadores.
*   **Eficiencia de Costos:** Backend totalmente serverless que incurre en costo cero durante períodos de inactividad.
*   **Bucle de Juego Sin Estado (Stateless Game Loop):** Diseño innovador del motor de juego que mantiene un estado continuo sin instancias de cómputo persistentes.
*   **Mecánicas Competitivas:** Implementa validación del lado del servidor para física, colisiones y puntuación para prevenir trampas.

---

## Arquitectura Técnica

El sistema implementa un patrón de **API Gateway con WebSockets** integrado con un **Bucle de Juego basado en Lambda**.

### Diagrama de Arquitectura

El flujo de datos asegura una comunicación de baja latencia mientras mantiene la integridad de los datos a través de almacenamiento NoSQL de alto rendimiento.

```mermaid
graph TD
    User((Jugador)) -->|Conexión WebSocket| APIG[API Gateway (WSS)]
    
    subgraph "Capa de Eventos"
        APIG -->|Conectar/Desconectar| ConnectionHandler[Lambda ConnectionHandler]
        APIG -->|Acción de Entrada| DynamoDB
    end
    
    subgraph "Capa de Matchmaking"
        ConnectionHandler -->|Unirse a Cola| SQS[Amazon SQS]
        SQS -->|Disparador| Matchmaker[Lambda Matchmaker]
        Matchmaker -->|Crear Partida| DynamoMatches[(DynamoDB Matches)]
    end
    
    subgraph "Capa del Motor de Juego"
        Matchmaker -->|Invocación Asíncrona| GameLoop[Lambda GameLoop Handler]
        GameLoop <-->|Leer Entradas / Escribir Estado| DynamoMatches
        GameLoop -->|Difundir Estado (200ms)| APIG
        APIG -->|Actualizar UI| User
    end
```

### Desglose de Componentes

| Componente | Funcionalidad |
| :--- | :--- |
| **API Gateway (WebSocket)** | Gestiona conexiones persistentes full-duplex entre clientes y el backend. |
| **Lambda ConnectionHandler** | Maneja los eventos del ciclo de vida de la conexión y encola solicitudes de ingreso. |
| **Lambda Matchmaker** | Procesa la cola SQS para agrupar jugadores e inicializa el estado de la partida en la base de datos. |
| **Lambda GameLoopHandler** | **Motor Central.** Ejecuta la simulación de física y actualizaciones de estado en un ciclo recursivo. |
| **DynamoDB** | Proporciona almacenamiento de latencia ultra baja para el estado del juego y las entradas de los jugadores, actuando como la "memoria" para las funciones sin estado. |

---

## Estructura del Proyecto

El repositorio está organizado en lógica de backend, código cliente de frontend y documentación.

```text
/aws-serverless-snake
│
├── /backend            # Funciones Serverless (Python)
│   ├── gameConnectionHandler.py   # Gestión del Ciclo de Vida WebSocket
│   ├── gameMatchmaker.py          # Lógica de Matchmaking y Procesamiento de Colas
│   └── gameLoopHandler.py         # Motor de Física y Difusión de Estado
│
├── /frontend           # Aplicación Cliente
│   └── index.html                 # Aplicación de Página Única (HTML5 Canvas + JS)
│
└── /docs               # Documentación Suplementaria
```

---

## Instrucciones de Despliegue

### Requisitos Previos

*   Cuenta de AWS Activa.
*   Rol de IAM configurado con permisos de mínimo privilegio para la ejecución de Lambda, DynamoDB y API Gateway.

### Paso 1: Despliegue del Backend

1.  **Base de Datos:** Crear una tabla en **DynamoDB** llamada `GameMatches` con `matchId` (String) como Clave de Partición (Partition Key).
2.  **API:** Desplegar una API WebSocket en **API Gateway**.
3.  **Funciones:** Desplegar las tres funciones Lambda encontradas en el directorio `/backend`.
    *   *Nota de Configuración:* Asegúrese de que el tiempo de espera (timeout) de `gameLoopHandler` esté configurado en **10 minutos** (600 segundos) para acomodar la duración completa de la partida.
4.  **Enrutamiento:** Configurar las rutas de API Gateway (`$connect`, `$disconnect`, `joinQueue`, `playerMove`) para apuntar a las funciones Lambda respectivas.

### Paso 2: Configuración del Frontend

1.  Abrir `/frontend/index.html`.
2.  Actualizar la constante `WSS_URL` con su Endpoint WebSocket de API Gateway desplegado.
3.  Desplegar el archivo cliente en un Bucket S3 configurado para Alojamiento de Sitios Web Estáticos, o ejecutar localmente para pruebas.

---

## Guía de Uso

1.  Navegue a la URL del cliente desplegado.
2.  Seleccione **"Unirse a la Cola"** (Join Queue) para entrar al grupo de emparejamiento.
3.  El tiempo de espera calculado depende del conteo de jugadores activos (o utilice una pestaña secundaria del navegador para simular un oponente).
4.  **Controles:** Utilice las Flechas del Teclado para dirigir la serpiente.
5.  **Objetivo:** Consumir objetivos para incrementar longitud y puntuación. Evite colisiones con paredes y oponentes.
6.  **Condición de Victoria:** Alcance 500 puntos para terminar la partida.

---

## Reconocimientos

Este proyecto fue arquitecturado e implementado como proyecto final (capstone) para el currículo de Computación en la Nube.

**Autores:**
* Andru Alexis Gómez Serna
* Edwin Santiago Posada Jaramillo
---

