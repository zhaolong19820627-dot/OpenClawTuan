# 图安工作知识库网站（TuanKB）

基于 `/mnt/tuan` 自动建立三级知识库页面，并支持夜间自动更新。

## 功能

- 一级目录：汇报PPT、解决方案文档、招标文档、投标文档、报价文档（仅 Excel）、合同文档、标准规范、视频、其他
- 二级目录：按项目名称合并索引（同项目聚合）
- 三级详情：文档缩略图、预览、下载
- 标书编制页：上传招标文件后自动生成“供应商/评分/编制”分析表
- 行业标签筛选（一级/二级）
  - AI赋能（AI视频分析一体机、应急大模型、化工园区AI赋能、应急领域AI赋能、其他）
  - 安全生产（HSE、安全生产标准化、重大危险源、双重预防、特殊作业、人员定位、承包商、教育培训、6+5、其他）
  - 智慧园区（化工园区、经开区、其他）
  - 应急管理（应急指挥、应急演练、应急推演、其他）
  - 车路协同（智慧高速、智慧隧道、智慧桥梁、智慧服务区、智慧收费站、智慧停车场、无人驾驶训练场、其他）
  - 其他行业
- 异常时间戳容错：统一回退标记 `2025-12-30 00:00:00`

## 目录

- `index.html` 前端页面
- `scripts/build_index.py` 索引构建脚本
- `scripts/server.py` 站点服务（含搜索与下载接口）
- `data/kb.json` 生成的索引数据

## 本地运行

```bash
cd TuanKB
python3 scripts/build_index.py
./scripts/start.sh
```

默认地址：`http://<服务器IP>:18893/`

停止：

```bash
cd TuanKB
./scripts/stop.sh
```

## API

- 搜索：`/api/search?q=关键词`
- 钉钉检索文本：`/api/dingtalk_search?q=关键词`
- 预览：`/preview?path=<绝对文件路径>`
- 下载：`/download?path=<绝对文件路径>`
- 标书分析（JSON）：`POST /api/bid/analyze`（multipart file）
- 标书分析并生成PDF：`POST /api/bid/analyze_pdf`（multipart file）

## 自动更新

已配置每日 02:00（Asia/Shanghai）自动执行：

```bash
python3 scripts/build_index.py
```
