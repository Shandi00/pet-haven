# 文件索引

請先閱讀 [專案首頁](../README.md)、[開發指南](guides/DEVELOPMENT.md)與[整理規則](guides/PROJECT_ORGANIZATION.md)。指令預設從專案根目錄執行。

## 期末專題（2026-12-09 展示）

- [開發指引 AGENTS.md](../AGENTS.md)：組員與 AI 工具共用的流程、分支與規則
- [需求與展示範圍](superpowers/specs/2026-11-25-需求與展示範圍-design.md)：任務 01 到 22 的需求來源
- [現況架構](architecture/現況架構.md)：既有系統的架構、資料模型、API 與已知缺口
- [架構圖與使用案例圖](architecture/diagrams/)：PlantUML 原始檔與輸出的 SVG

## 開發與維護

- [開發指南](guides/DEVELOPMENT.md)：安裝、啟動、測試、常見問題
- [環境設定](guides/ENVIRONMENT.md)
- [示範資料載入](guides/DATA_LOADING_GUIDE.md)
- [專案整理規則](guides/PROJECT_ORGANIZATION.md)

## 功能

- [Google 登入](auth/GOOGLE_LOGIN.md)
- [政府資料匯入指南](data-import/資料匯入指南.md)
- [政府資料匯入與審核測試流程](data-import/政府資料匯入與審核測試流程.md)
- [功能清單](features/FEATURE_CHECKLIST.md)
- [送養功能更新說明](features/送養功能更新說明.md)
- [管理員編輯功能說明](features/管理員編輯功能說明.md)

## 測試、API 與部署

- [後端測試說明](../backend/README_TESTING.md)
- [QA 測試計畫](../backend/QA_TEST_PLAN.md)
- [P0 測試設計](../backend/TEST_DESIGN_P0.md)
- [Swagger API 文件](../backend/SWAGGER_API_DOCS.md)
- [日誌管理](../backend/LOGGING.md)
- [貼文清理腳本](../backend/scripts/CLEANUP_GUIDE.md)
- [前端 E2E 指南](../frontend/E2E_TESTING_GUIDE.md)
- [錯誤邊界說明](../frontend/ERROR_BOUNDARY.md)
- [共用 UI 元件](../frontend/src/components/ui/README.md)
- [部署檢查表](deployment/deployment-checklist.md)
- QA gates 與追溯評估：docs/qa/gates、docs/qa/assessments

## 其他

- [10 分鐘提案簡報大綱](presentation/提案簡報大綱_10分鐘.md)（早期試營運版本，與 10/21 提案簡報不同，期末簡報會依需求文件重寫）

歷史測試、修復與實作報告已從版本庫移除，需要時可在 git 歷史（commit 3a6df08）查閱；目前狀態以重新執行測試為準。
