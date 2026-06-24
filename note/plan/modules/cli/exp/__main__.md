# `cli/exp/__main__.py`

## 模組責任

`cli/exp/__main__.py` 是 `python -m ...cli.exp` 的最薄啟動層。它只負責把模組執行轉交給 `main()`。

## 公開入口/主要類型

- `main`
- `if __name__ == "__main__": main()`

## 主要資料結構與資料契約

- 沒有自己的設定或資料模型。
- 完全依賴 `cli/exp/main.py` 的預設路徑與 evaluator 註冊邏輯。

## 資料流與控制流

1. 使用者執行 `python -m ...cli.exp`。
2. Python 進入 `__main__.py`。
3. 本模組呼叫 `main()`，之後所有流程都交由 `cli/exp/main.py`。

## 失敗路徑與例外條件

- 沒有自己的錯誤處理；任何錯誤都直接來自 `main()` 下游。

## 副作用與資源生命週期

- 無獨立副作用。
- 真正的 collect/output 副作用都在 `main()` 裡觸發。

## 與其他模組的關係

- 上游：Python 模組執行機制。
- 下游：`cli/exp/main.py`。

## 對應函式索引與閱讀順序

1. `main`
2. module runner block
