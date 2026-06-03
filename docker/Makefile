.PHONY: up down build logs ps restart-backend restart-frontend

COMPOSE ?= docker compose
ENV_FILE ?= .env

up:
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

build:
	$(COMPOSE) --env-file $(ENV_FILE) build

logs:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f

ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

restart-backend:
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build backend

restart-frontend:
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build frontend
