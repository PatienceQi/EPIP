# 部署指南

本指南介绍在不同环境下部署本项目的推荐流程，并提供运维监控、备份和故障排查的常用步骤。

## 1. 环境要求

- Docker 版本：20.10 及以上，推荐使用最新稳定版。
- 系统资源：内存不少于 4 GB；磁盘空间预留 20 GB 以上用于镜像、日志和备份。
- 命令工具：`docker`, `docker compose` (或 `docker-compose`)，`make`。

## 2. Docker 开发部署

1. 确保 `docker-compose.yml` 中的默认镜像、端口和挂载目录满足本地开发需求。
2. 在项目根目录执行：
   ```bash
   docker compose up --build
   ```
   支持使用 `-d` 以后台方式启动，首次运行会自动构建镜像。
3. 更新代码后可运行 `docker compose restart <服务名>` 重载单个服务。
4. 通过 `docker compose logs -f <服务名>` 实时查看容器输出，确认启动无误。

## 3. Docker 生产部署

生产环境使用 `docker-compose.prod.yml` 搭配 `.env.prod`：

1. 根据部署目标服务器的资源，调整 `docker-compose.prod.yml` 中的副本数、资源限制及卷挂载。
2. 在 `.env.prod` 中填充所有敏感配置，并确保该文件仅在服务器上可读。
3. 以只读配置运行：
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
   ```
4. 升级时建议使用 `docker compose ... pull && docker compose ... up -d`，确保服务平滑滚动更新。

## 4. 环境变量配置详解

所有可用的环境变量、默认值及说明均集中在 `docs/configuration.md` 中。部署前请逐项核对必填项，尤其是数据库、消息队列、第三方服务凭证等。若需新增变量，应同步在该文档中补充说明，保持配置与文档一致。

## 5. 健康检查与监控

部署后应将以下 HTTP 端点接入负载均衡或监控系统：

- `/monitoring/health/live`：存活探针，返回 200 表示进程运行正常。
- `/monitoring/health/ready`：就绪探针，用于判断服务依赖（数据库、缓存）是否可用。
- `/monitoring/metrics`：Prometheus 兼容指标端点，可接入 Prometheus/Grafana 进行可视化监控。

建议在 Kubernetes 或其它编排平台中，将存活探针与就绪探针分别映射为 liveness/readiness checks，以减少无效流量和自动重启时间。

## 6. 日志管理

- 所有服务输出统一写入 Docker 日志，可通过 `docker logs <容器ID或名称>` 查看。
- 日志采用 JSON 格式，便于被 ELK、Loki 等日志聚合系统收集解析。
- 建议为生产环境启用 `--log-opt max-size`、`--log-opt max-file` 等 Docker 日志轮转参数，避免磁盘被日志占满。

## 7. 数据备份与恢复

- 执行 `make backup`：触发脚本导出数据库及关键持久化数据到默认备份目录（通常在 `data/backups/`）。确保对该目录进行外部归档或挂载远程存储。
- 执行 `make restore`：从最近一次备份中恢复数据，恢复前请确认服务处于停机或维护窗口，避免写入冲突。
- 建议在 CRON 或 CI/CD 中配置定期执行 `make backup`，并在恢复演练中验证备份有效性。

## 8. 故障排查清单

常见问题与解决方案：

1. **容器无法启动**：使用 `docker compose logs -f <服务名>` 查看启动日志，重点检查端口冲突、依赖服务未运行、环境变量缺失等错误。
2. **数据库连接失败**：确认 `.env`/`.env.prod` 中的数据库地址和凭证正确，防火墙或安全组允许访问，对应数据库容器已启动且健康。
3. **内存或磁盘不足**：执行 `docker system df` / `docker system prune` 清理无用镜像，或在宿主机上扩容资源；同时检查日志轮转与临时文件目录。
4. **健康检查失败**：直接访问健康端点以获取详细错误消息，必要时查看应用日志定位依赖异常。
5. **备份或恢复异常**：确认 `make` 命令使用的脚本具备相应权限，备份目录可读写，且容器卷正确挂载。

通过以上步骤可快速定位大多数部署故障，复杂问题请结合监控告警和详细日志进一步分析。
