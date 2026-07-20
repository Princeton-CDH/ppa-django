# PPA Reuse — 开发 TODO

> 按优先级分层。每层内部按重要性排序。

---

## 第一层：完成现有设计的"最后一公里"

- [ ] **Solr schema 自动化命令**
  新增 `python manage.py update_solr_schema --adapter <name>` 命令，把 `adapter.yaml` 里的 `solr_schema` 配置直接 apply 到 Solr，消除每次新增适配器字段时的手动操作。

- [ ] **adapter.yaml 完整验证**
  加强 `loader.py` 的 YAML 验证：检查 `field_map` 里的路径是否真实存在于模型、`solr_schema` 字段名是否与已有字段冲突。新用户写错 YAML 时应给出明确报错，而不是沉默失败。

- [ ] **IA 全文页面索引接入 `page_index_data()`**
  `DigitizedWork.page_index_data()` 还没适配 Internet Archive 的 DjVu/hOCR 格式，导致 IA 文本的 "search within a work" 功能不起作用。需要把 `InternetArchiveAPI.get_item_pages()` 的输出接入页面索引管道。

- [ ] **修复 `pub_place` 字段提取 bug**
  `internet_archive.py:338` 把 `publisher` 字段误用作 `pub_place` 的 fallback，两个字段含义不同。IA 元数据里 `publisher` 存的是出版商名字，不是地点。

---

## 第二层：让新用户真正能独立接入新数据集

- [ ] **完整的 HOWTO 文档**
  以 `ia_prosody` 为 worked example，写从零到能搜索的完整流程：创建适配器 YAML → 安装 Solr schema → 导入数据 → 验证搜索。目标读者是第一次接触本项目的 DH 开发者。

- [ ] **Facet 配置驱动化**
  把 `ArchiveSearchView` 里硬编码的 `facet_fields` 移到 `adapter.yaml`，让适配器能声明自己的 facet 字段、标签和显示顺序。这是"零核心代码改动接入新数据集"真正成立的最后一块拼图。

- [ ] **多适配器同时运行**
  `ARCHIVE_ADAPTER` 目前是单一全局设置。`get_adapters_for_work()` 已经支持按 collection 路由，但 `context_processor` 只返回全局单一适配器，视图层也未完整实现。需要让同一实例里不同 collection 能使用不同适配器，context 按当前请求的 collection 动态切换。

- [ ] **`local_settings.py.sample` 样板文件**
  `GENERALIZATION_GOALS.rst` 提到但至今没有。新部署者拿到代码不知道最小可用配置是什么，需要一个有完整注释的样板覆盖所有可选配置项（数据库、Solr、waffle 开关、适配器路径等）。

- [ ] **各数据源档案格式文档**
  在文档中补充每个已支持/计划支持的数据源所拉取档案的格式类型，方便新用户上手。内容包括：
  - **Internet Archive**：元数据 JSON（Metadata API）+ 全文三种格式（DjVu XML / hOCR HTML / 纯文本），各格式的结构、页边界支持情况、质量差异
  - **HathiTrust**：MARC + METS pairtree，ZIP 内的 OCR txt 文件（每页一个），`*.mets.xml` 描述结构
  - **Gale/ECCO**：MARC/CSV 元数据 + 可选本地 OCR（XML 格式）
  - **EEBO-TCP / ECCO-TCP**（计划中）：TEI XML，标准化程度高，适合直接解析
  - **Project Gutenberg**（计划中）：RDF 元数据 + UTF-8 纯文本/HTML/EPUB
  - 每种格式注明：是否有页边界、是否需要认证、OCR 质量预期、现有解析器状态

---

## 第三层：代码质量与技术债

- [ ] **修复 3 个预先存在的测试失败**
  `TestCollection::test_stats`、`TestEditorialIndexPage::test_template_rendering`、`TestCollectionPage::test_template` 在本项目工作开始前就已失败。这让 CI 失去可信度——总是红的测试会掩盖新引入的 failure。

- [ ] **Sass `@import` 迁移到 `@use`/`@forward`**
  目前用 `silenceDeprecations: ['import']` 压住了 34 处 `@import` 的 deprecation warning。Dart Sass 3.0 发布后这些会直接 break。需要专项迁移，工作量可估算（34 处 `@import`，涉及 `_variables.scss` 和 `_mixins.scss` 的命名空间前缀化）。

- [ ] **`requirements.txt` 版本上限定期 review**
  `wagtail<7.1,>=7.0`、`beautifulsoup4<=4.11` 等硬上限在新版本发布后会让 `pip install` 静默锁在旧版。建议建立季度 review 机制，或用 `dependabot` 自动提 PR。

---

## 第四层：新功能方向（对应 GENERALIZATION_GOALS 和 DH2026）

- [ ] **EEBO-TCP / TEI 适配器**
  TEI/TCP 格式标准化程度高、覆盖历史英语语料库的核心来源（EEBO-TCP、ECCO-TCP），是继 IA 之后工作量可控的下一个数据源。需要 TEI XML 解析器 + 适配器 YAML + 示例数据集。

- [ ] **Wagtail editorial 模块化**
  `EditorialPage`、`ContributorsPage` 等 Wagtail page types 目前是硬编码的 Princeton PPA 内容结构。把这些做成可选的 Wagtail app，让新部署能选择性启用，是 GENERALIZATION_GOALS 里"CMS/editorial 模块化"目标的核心。

---

## 参考

- [`GENERALIZATION_GOALS.rst`](GENERALIZATION_GOALS.rst) — 项目泛化设计目标
- [`SOFTWARE_PAPER_OUTLINE.md`](SOFTWARE_PAPER_OUTLINE.md) — CHR 论文结构（DH2026）
- [`CHANGES_SUMMARY.md`](CHANGES_SUMMARY.md) / [`CHANGES_SUMMARY.html`](CHANGES_SUMMARY.html) — 已完成改动记录
- [`IMPLEMENTATION_GUIDE.md`](IMPLEMENTATION_GUIDE.md) — 实现细节
