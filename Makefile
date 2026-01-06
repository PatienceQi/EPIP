.PHONY: install test lint format run clean docker-build docker-up docker-down docker-logs docker-up-llm deploy-prod deploy-prod-down logs-prod backup restore frontend-install frontend-dev frontend-build build-all

install:
	pip install -e '.[dev]'

test:
	pytest tests/ -v --cov=src/epip --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

run:
	uvicorn epip.main:app --reload

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

build-all: frontend-build
	mkdir -p src/epip/static
	find src/epip/static -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} +
	cp -R frontend/dist/. src/epip/static/

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

# Docker commands
docker-build:
	docker compose -f docker/docker-compose.yml build

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-logs:
	docker compose -f docker/docker-compose.yml logs -f

docker-up-llm:
	docker compose -f docker/docker-compose.yml --profile llm up -d

# Production deployment commands
deploy-prod:
	docker compose -f docker/docker-compose.prod.yml up -d --build

deploy-prod-down:
	docker compose -f docker/docker-compose.prod.yml down

logs-prod:
	docker compose -f docker/docker-compose.prod.yml logs -f

backup:
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
		backup_dir="$(CURDIR)/backups"; \
		mkdir -p "$$backup_dir"; \
		echo "Creating backup $$timestamp in $$backup_dir"; \
		docker run --rm -v neo4j_data:/data -v "$$backup_dir":/backups alpine tar -czf /backups/neo4j_data_$${timestamp}.tar.gz -C /data .; \
		docker run --rm -v redis_data:/data -v "$$backup_dir":/backups alpine tar -czf /backups/redis_data_$${timestamp}.tar.gz -C /data .

restore:
	@set -e; \
		backup_dir="$(CURDIR)/backups"; \
		neo4j_backup="$(RESTORE_NEO4J)"; \
		redis_backup="$(RESTORE_REDIS)"; \
		if [ -n "$(RESTORE_TIMESTAMP)" ]; then \
			neo4j_backup="$$backup_dir/neo4j_data_$(RESTORE_TIMESTAMP).tar.gz"; \
			redis_backup="$$backup_dir/redis_data_$(RESTORE_TIMESTAMP).tar.gz"; \
		fi; \
		if [ -z "$$neo4j_backup" ]; then \
			neo4j_backup=$$(ls -t "$$backup_dir"/neo4j_data_*.tar.gz 2>/dev/null | head -n 1); \
		fi; \
		if [ -z "$$redis_backup" ]; then \
			redis_backup=$$(ls -t "$$backup_dir"/redis_data_*.tar.gz 2>/dev/null | head -n 1); \
		fi; \
		if [ -z "$$neo4j_backup" ] || [ ! -f "$$neo4j_backup" ]; then \
			echo "Neo4j backup not found. Provide RESTORE_TIMESTAMP or RESTORE_NEO4J=<path>."; \
			exit 1; \
		fi; \
		if [ -z "$$redis_backup" ] || [ ! -f "$$redis_backup" ]; then \
			echo "Redis backup not found. Provide RESTORE_TIMESTAMP or RESTORE_REDIS=<path>."; \
			exit 1; \
		fi; \
		echo "Restoring $$neo4j_backup and $$redis_backup"; \
		docker run --rm -v neo4j_data:/data -v "$$backup_dir":/backups alpine sh -c "rm -rf /data/* && tar -xzf /backups/$$(basename \"$$neo4j_backup\") -C /data"; \
		docker run --rm -v redis_data:/data -v "$$backup_dir":/backups alpine sh -c "rm -rf /data/* && tar -xzf /backups/$$(basename \"$$redis_backup\") -C /data"
