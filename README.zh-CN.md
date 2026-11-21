# Wearable Mobility Research Pipeline v1.0.0

**定位：** 为科研软件 / Research Programmer / GIS 岗位展示可运行的 GPS 数据管道与空间分析能力。此项目与 USC、Fitbit 或真实科研机构无关联，也不包含实际佩戴者或患者数据。

## Windows 上怎么运行

1. 解压 ZIP，在 VS Code 里打开文件夹 `wearable_mobility_research_v0_1`。
2. 确保安装 Python 3.11 或以上，且终端里 `py -3 --version` 能正常运行。
3. 双击 `scripts/start_windows.bat`，或在 VS Code 终端执行 `scripts\start_windows.bat`。首次启动需联网安装 Python 依赖。
4. 浏览器打开 `http://127.0.0.1:8000`。API 文档：`http://127.0.0.1:8000/docs`。
5. 用 `Ctrl+C` 停止服务。测试使用 `scripts/test_windows.bat`。

**注意：** 首次启动会生成 `data/synthetic_wearable.csv`（包里已附）和本地 SQLite 数据库 `mobility.db`。再次启动不会清空旧数据。Leaflet 由本地服务提供。默认底图需要网络；Python API 本地运行无需密钥。

## 目前已经实现的部分

- 3 个虚构参与者、2 天、366 条模拟 GPS/步数/心率数据。
- CSV 导入、UTC 时间标准化、坐标范围校验、去重、拒绝原因和导入记录。
- SQLite 为默认存储，并在隔离的 MySQL 9.0 实例上验证了迁移和导入。
- Haversine 距离、异常速度筛查、固定半径停留点、GeoPandas 投影面积计算与 GeoJSON。
- FastAPI API、可筛选地图 Dashboard、CSV 下载。
- Pytest 后端检查。

## 当前还没有实现的部分

- **没有**真实 Fitbit API 接入、移动端 SDK、真实研究数据、临床研究验证。
- **没有**正式登录权限、PHI 防护或医疗合规认证。
- 地图与每日指标用于解释演示轨迹。按计划采样频率评估 GPS 覆盖率及正式研究统计模型仍待实现。

## 交给 Codex 的顺序

打开 `AGENTS.md`、`docs/CODEX_HANDOFF.md`、`docs/PROJECT_SPEC.md`，让 Codex **增量开发**，不新建替代项目，保留现有代码、数据库、页面和测试。建议先做 P0 的数据管道质量与科学可复现性，再完善图层和可视化，最后才做 MySQL / 模拟 Fitbit 适配器。

> 不要把此作品集描述成已处理患者数据、真实 Fitbit 接入、医院部署或实际发表的研究成果。只有已完成、经过验证的功能才能写进简历。

## 增量版本

- CSV 流式读取，每 400 条分批校验和去重。导入批次记录 SHA-256、耗时与计数，拒绝原因可在浏览器按批次筛选。
- Alembic 自动升级 SQLite 历史数据。默认统计日为 UTC，设置 `STUDY_TIMEZONE` 可用指定 IANA 时区。
- 地图支持图层开关，且与每日统计使用相同的参与者和日期。可导出观测 CSV、每日指标 CSV、各图层 GeoJSON 及分析元数据 JSON。
- Leaflet 静态资源已本地化。使用 `/?basemap=none` 可查看无底图的本地矢量地图。
- 最近运行结果和截图见 [验收报告](docs/TEST_REPORT.md) 与 [英文 README](README.md)。已通过独立 MySQL 实例验证，已保存接受记录的原始字段及批次来源。研究队列管理和派生空间质量标记的历史持久化仍待完成。

GPS 观察有效率与预期采样覆盖率已分开。缺少研究采样配置时，预期采样覆盖率显示 N/A。见[发布验收报告](docs/RELEASE_REPORT.md)。
