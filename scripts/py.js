// 用 backend/.venv 的 Python 執行參數，讓 npm 指令在 Windows 與 Linux 寫法相同
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const backendDir = path.join(__dirname, '..', 'backend');
const python = path.join(
  backendDir,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'
);

if (!fs.existsSync(python)) {
  console.error('找不到 backend/.venv，請先執行 npm run setup');
  process.exit(1);
}

const result = spawnSync(python, process.argv.slice(2), { cwd: backendDir, stdio: 'inherit' });
process.exit(result.status ?? 1);
