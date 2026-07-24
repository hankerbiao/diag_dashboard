# 便捷入口：委托 docker/ 目录
.PHONY: dev up down build logs docker-%

DOCKER_MAKE = $(MAKE) -C docker

dev:
	./scripts/start_dev.sh

up down build logs ps restart-backend restart-frontend:
	$(DOCKER_MAKE) $@

docker-up:
	$(DOCKER_MAKE) up
