import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// 2026-11-28 由 react-scripts（Create React App，已停止維護）改用 Vite 與 Vitest（T21 套件漏洞）。
// 沿用 CRA 的設定，組員的 .env、Dockerfile、Playwright 設定都不用改：
// 環境變數用 REACT_APP_ 開頭、開發埠 3000、建置輸出到 build/。
// 和 CRA 不同的是，有 JSX 的檔案要用 .jsx 副檔名（Vite 不轉換 .js 裡的 JSX）。
export default defineConfig({
  plugins: [react()],
  envPrefix: 'REACT_APP_',
  server: {
    port: 3000,
    strictPort: true,
    // 原本的 src/setupProxy.js
    proxy: { '/api': { target: 'http://localhost:5000', changeOrigin: true } },
  },
  build: { outDir: 'build' },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
    include: ['src/**/*.test.{js,jsx}'],
    // 同 CRA 的 resetMocks：每個測試前重設 mock，測試之間不互相影響
    mockReset: true,
  },
});
