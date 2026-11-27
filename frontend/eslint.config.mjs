import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

// 取代 react-scripts 內建的 eslint-config-react-app：和它一樣，Hooks 用法錯誤與未定義的變數算錯誤，其餘只警告。
// 執行：npm run lint
const warnOnly = Object.fromEntries(Object.keys(js.configs.recommended.rules).map((rule) => [rule, 'warn']));

export default [
  { ignores: ['build/', 'playwright-report/', 'test-results/'] },
  // 程式裡有為 CRA 規則寫的 eslint-disable 註解，這裡不再提醒「沒用到」
  { linterOptions: { reportUnusedDisableDirectives: 'off' } },
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: globals.browser,
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...warnOnly,
      'no-undef': 'error',
      // 新版 JSX 轉換不需要 React 變數，但既有檔案都還有 import React
      'no-unused-vars': ['warn', { args: 'none', ignoreRestSiblings: true, varsIgnorePattern: '^React$' }],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
  {
    files: ['src/**/*.test.{js,jsx}', 'src/setupTests.js'],
    languageOptions: { globals: { ...globals.browser, ...globals.node, ...globals.vitest } },
  },
  {
    files: ['e2e/**/*.js'],
    // page.evaluate 裡的程式在瀏覽器執行，所以也有 window
    languageOptions: { sourceType: 'commonjs', globals: { ...globals.node, ...globals.browser } },
    rules: { ...warnOnly, 'no-undef': 'error' },
  },
];
