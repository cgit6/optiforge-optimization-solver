# `cli/convert/main.py`

## 模組責任

`cli/convert/main.py` 是 raw dataset 轉 problem YAML 的命令列入口。它只負責解析參數、掃描 `data/<dataset>`、挑選 parser，並逐檔呼叫 `transformToYaml(...)`。

## 公開入口/主要類型

- `_is_cb_bundle_file(...)`
- `build()`
- `main(...)`

## 主要資料結構與資料契約

- CLI 參數：
  - `--dataset`
  - `--converter`
  - `--repo-root`
- 輸入來源固定是 `repo_root / "data" / dataset` 下的 `.dat` 與 `.txt`。
- `main(...)` 回傳 `list[Path]`，表示實際產出的 YAML 路徑。
- `--converter` 的合法值完全來自 `converter.register` registry；本模組不自行判斷題庫格式。

## 資料流與控制流

1. `build()` 建立 `argparse.ArgumentParser`。
2. `main(...)` 解析 CLI，先驗證 `dataset` 非空且資料夾存在。
3. 依 `*.dat`、`*.txt` 掃描來源檔，並用 `_is_cb_bundle_file(...)` 排除 CB 題庫中與 dataset 同名的 bundle 檔。
4. 透過 `getConverter(...)` 取得 parser。
5. 逐檔呼叫 `transformToYaml(...)`，由 converter 層完成 parser 執行、`ProblemModel` 建立與 YAML 寫出。
6. 回傳全部輸出路徑，供外部程式或測試檢查。

## 失敗路徑與例外條件

- `dataset` 是空字串時，`main(...)` 直接丟 `ValueError`。
- `data/<dataset>` 不存在時丟 `FileNotFoundError`。
- 資料夾內沒有可用 `.dat`/`.txt` 時丟 `FileNotFoundError`。
- `--converter` 不合法通常會在 `argparse` 就被攔下；若外部程式直接呼叫並傳錯值，`getConverter(...)` 仍可能失敗。
- 任何單檔 parser 失敗或 YAML 寫出失敗，都會中斷整個批次轉換。

## 副作用與資源生命週期

- 會讀取 `data/<dataset>` 原始檔。
- 會透過 `transformToYaml(...)` 在 `configs/problems/...` 寫出 YAML。
- 會建立 `tqdm` progress bar；這是命令列副作用，不影響回傳資料契約。

## 與其他模組的關係

- 上游：`cli/convert/__main__.py`、外部 `python -m ...cli.convert`。
- 下游：`converter.getConverter(...)`、`converter.listConverters(...)`、`converter.transformToYaml(...)`。
- parser 實作實際在 [`cli/convert/register.py`](register.md)，寫檔邏輯在 [`converter/converter.py`](../../converter/converter.md)。

## 對應函式索引與閱讀順序

1. `build`
2. `_is_cb_bundle_file`
3. `main`
