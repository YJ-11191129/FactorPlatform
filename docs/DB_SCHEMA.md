# DB_SCHEMA

本文件从主设计文档拆分，定义：标准化数据表、因子元数据表、因子值表、任务与日志表的主键/索引/约束。

## 1. 标准化数据表

## 2. 因子元数据与因子值表

### 2.1 factor_metadata

- 作用：把“代码里可用的因子”同步成可查询的元数据目录，供前端展示与调度/分析引用。
- 主键：factor_key = lower(factor_name)::lower(version)

字段（MVP）：

- factor_key (PK)
- factor_name (index)
- version (index)
- category (index)
- display_name
- description
- python_entry
- dependencies (json)
- parameter_schema (json)
- status (index)
- owner
- created_at
- updated_at

### 2.2 factor_runs

- 作用：记录一次“计算并落地”的运行信息，artifact 目前落在本地 parquet（后续可切对象存储）。
- 主键：calc_batch_id

字段（MVP）：

- calc_batch_id (PK)
- factor_name (index)
- factor_version (index)
- mode (index)
- params (json)
- universe_name (index)
- provider_uri
- start_date / end_date (index)
- instrument_limit
- artifact_path
- row_count
- status (index)
- error
- computed_at (index)

## 3. 分析结果与报告归档表

### 3.1 analysis_results

- 作用：保存分析摘要（json）+ 工件目录（parquet/json/html 等）
- 主键：analysis_id
- 索引：analysis_type、calc_batch_id、factor_name、factor_version、status

### 3.2 report_artifacts

- 作用：保存报告归档（HTML/PDF 文件路径）与元信息
- 主键：report_id
- 索引：report_type、analysis_id、status

## 4. 任务与日志表

### 4.1 task_jobs

- 作用：任务中心的运行记录（由 Celery worker 执行，DB 作为统一真相源）
- 主键：job_id
- 索引：job_type、status、actor、celery_task_id

### 4.2 audit_logs

- 作用：请求级审计日志（actor、path、status_code、耗时等）
- 主键：id（自增）
- 索引：request_id、actor、role、action、resource、status_code

## 5. 索引与分区建议
