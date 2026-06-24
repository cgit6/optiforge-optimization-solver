# `tests/test_converter_registry.py`

## 模組責任

`test_converter_registry.py` 覆蓋 raw benchmark converter registry、parser 正確性與 `cli.convert` 的端到端轉檔行為。

## 公開入口/主要類型

- pytest 自動發現測試
- 主要 helper：`_write_weish_dat`
- 主要測試群：registry CRUD、parser payload、CLI 轉檔、skip/overwrite 規則

## 主要資料結構與資料契約

converter 必須能從 `.dat`/`.txt` 讀出正確 problem payload、註冊表要拒絕重複 key、CLI 轉檔要輸出可被 repository 載入的 YAML。

## 資料流與控制流

先測 registry CRUD，再對 WEISH/GK 等 parser 做 payload 驗證，最後走 `convert` CLI 檢查 YAML 寫出與 skip 規則。

## 失敗路徑與例外條件

未知 converter、重複註冊、parser 轉置錯誤、bundle file 誤轉或 CLI 未覆寫預期 YAML 都屬回歸。

## 副作用與資源生命週期

會在 `tmp_path` 產生原始 benchmark 檔與轉出的 YAML。

## 與其他模組的關係

目標模組是 `mkp.cli.convert`、`mkp.converter`、`mkp.engine.repository` 與 `mkp.problem`。

## 對應函式索引與閱讀順序

1. `_write_weish_dat`
2. `test_cli_converter_registry_has_expected_converters`
3. `test_get_unknown_converter_raises`
4. `test_register_duplicate_converter_raises`
5. `test_converter_core_writes_yaml_and_loads_model`
6. `test_parse_weish_transposes_weights`
7. `test_registered_dataset_parsers_read_expected_payloads`
8. `test_gk_parser_accepts_instances_without_best_known`
9. `test_get_converter_returns_new_parsers`
10. `test_convert_cli_converts_dataset_and_overwrites_yaml`
11. `test_convert_cli_converts_txt_dataset`
12. `test_convert_cli_skips_cb_bundle_file`

## 核心函式與 helper 說明

### `_write_weish_dat`

這個 helper 產生最小 `.dat` 測資，讓 converter 測試可以在隔離環境裡重建 raw dataset -> YAML -> repository load 的完整鏈路。

### registry / parser wiring 測試群

`test_cli_converter_registry_has_expected_converters`、`test_get_unknown_converter_raises`、`test_register_duplicate_converter_raises`、`test_get_converter_returns_new_parsers` 保護 converter registry 的公開介面與名稱衝突規則。

### parser payload 測試群

`test_parse_weish_transposes_weights`、`test_registered_dataset_parsers_read_expected_payloads`、`test_gk_parser_accepts_instances_without_best_known` 描述各資料集 parser 的輸入輸出契約，特別是權重矩陣方向與 `best_known=None` 的容忍。

### `test_converter_core_writes_yaml_and_loads_model` / convert CLI 測試群

這組案例把 raw data、`transformToYaml(...)`、`cli.convert.main(...)` 與 `ProblemRepository.load(...)` 串起來。它們保護的是資料轉換鏈，而不是單純的 parser 細節。
