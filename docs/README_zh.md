# SQL Schema AI Exporter：中文使用说明

独立项目建议 GitHub 仓库名：`sql-schema-ai-exporter`。

## 功能边界

仅导出 SQL Server 指定 Database 中有权查看的 User Tables、Views 和各自的字段名称（保留 Schema、对象类型、字段顺序与数据库名称）。**不读取业务数据行**，不提取数据类型、索引、PK/FK 或存储过程定义。对于权限不足导致不可见的对象，不能声称整个数据库完整。

## Windows 安装

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[sql,test]"
```

需在 Windows 安装 Microsoft ODBC Driver 18 for SQL Server；工具不依赖 Playwright/Chromium。可使用 Windows Integrated Authentication：

```powershell
.\.venv\Scripts\python.exe -m sql_schema_ai_exporter `
  --server "SQL-SERVER\\INSTANCE" --database "ASAP_DB" `
  --auth windows --out "D:\Exports\ASAP_DB_Schema"
```

SQL 用户名密码登录：

```powershell
.\.venv\Scripts\python.exe -m sql_schema_ai_exporter `
  --server "SQL-SERVER" --database "ASAP_DB" `
  --auth sql --user "ACCOUNT" --out "D:\Exports\ASAP_DB_Schema"
```

程序会在终端安全提示输入密码（不回显），不会保存到输出文件。也支持 `--password-env VAR_NAME`，用于已有的组织批准的安全凭据流程。默认加密连接并校验证书；只有公司允许时才传 `--trust-server-certificate`。

## 已有 Metadata CSV 时离线出图（最简方式）

如果在 VS Code/SSMS 中已执行只读 Catalog 查询，可导出结果为包含表头的 UTF-8 CSV，然后运行：

```powershell
.\.venv\Scripts\python.exe -m sql_schema_ai_exporter `
  --input .\examples\schema_sample.csv `
  --out .\output `
  --mode balanced
```

请使用 `schema_sample.csv` 中的表头和 `T/V` 代码。离线还支持该工具导出的 `schema_snapshot.json`，支持先提取后离线反复优化排版。

## 图片密度模式

- `balanced`：2400×3200、3 栏、20 px 字体，默认推荐。
- `dense`：2800×3600、4 栏、18 px 字体，更省图片。
- `readable`：2000×2800、2 栏、22 px 字体，更容易阅读。

可以指定 `--width --height --columns --font-size --theme dark` 调整。SQL 名称较长时减少栏数。每个对象用 `T/V schema.object` 作为标题；字段在紧凑段落中排列；不能截断的超长字段逐字符续行，跨页时重复对象标题并标注续页。超过整栏宽度的对象名会明确报错而不是悄悄截断，此时使用更少栏数或更小字体。

如果中文字段显示方块，请指定字体：`--font-path "C:\Windows\Fonts\msyh.ttc"`。

## 输出

- `data/schema_snapshot.json`：完整准确的结构化版本，AI 精确查询的主要来源。
- `data/objects.jsonl`、`data/columns.jsonl`、`data/schema_columns.csv`：可机器处理字段。
- `docs/schema_catalog.md`：保留完整对象和字段的文字文档。
- `images/schema_*.png`：多栏高密度视觉版本。
- `images/image_manifest.csv`：图片与对象/字段编号对照。
- `export_report.json`：覆盖率、图片数量、快照 SHA256。100% 表示版面逻辑完整，不意味着任何视觉模型 100% 读对。

## 注意

元数据也可能属于公司专有系统信息，未经批准不得上传个人 GitHub、ChatGPT 或其他外部云服务；Private Repository 不是自动授权。建议把工具源码和真实 Schema 导出文件分开存放。输出目录默认在 `.gitignore` 中忽略。
