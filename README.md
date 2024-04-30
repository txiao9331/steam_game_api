# 🎮 Steam Store Game API 🎮

## Overview
Welcome to the Steam Store Game API! This API provides access to information about games available on the Steam Store. Explore the world of gaming through a simple RESTful interface.

## Usage
1. **Authentication**: No authentication is currently required to access the endpoints of this API.
2. **Endpoints**:
   - **GET `/v1/games/{appid}`**: Retrieve a game from the Steam Game dataset by its appID.
   - **DELETE `/v1/games/{appid}`**: Delete a game from the Steam Game dataset by its appID.
   - **GET `/v1/games`**: Retrieve all games from the Steam Store.
   - **POST `/v1/games`**: Add data of a new game to the dataset.
3. **Interactive Documentation**: Explore and interact with the API using Swagger UI. Simply run the application and navigate to the Swagger UI documentation URL.

## Installation
To run this API locally, follow these steps:
1. Install Python (if not already installed).
2. Clone this repository.
3. **Include `config.json`**: Ensure that the `config.json` file, containing sensitive configuration details, is included in the project directory. If using Git, make sure it's not listed in `.gitignore`.
4. Install the required dependencies listed in `requirements.txt` by running:
