const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let pyProc = null;
let mainWindow = null;

function startBackend() {
  const isDev = !app.isPackaged;
  const backendDir = path.join(__dirname, 'backend');

  if (isDev) {
    console.log('Spawning backend in dev mode...');
    // Spawns backend using Windows command line wrapper
    pyProc = spawn('py', ['-m', 'uvicorn', 'main:app', '--port', '8000'], {
      cwd: backendDir,
      shell: true
    });
  } else {
    console.log('Spawning backend in production mode...');
    // Locate the bundled executable in resource path (main/main.exe)
    const exePath = path.join(process.resourcesPath, 'main', 'main.exe');
    pyProc = spawn(exePath, [], {
      cwd: path.dirname(exePath),
      shell: true
    });
  }


  pyProc.stdout.on('data', (data) => {
    console.log(`Backend stdout: ${data}`);
  });

  pyProc.stderr.on('data', (data) => {
    console.error(`Backend stderr: ${data}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  const isDev = !app.isPackaged;
  if (isDev) {
    // Connect to the local React dev server during dev
    mainWindow.loadURL('http://localhost:5173');
  } else {
    // Load local built index.html in production
    mainWindow.loadFile(path.join(__dirname, 'frontend/dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pyProc) {
    console.log('Terminating backend process tree...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', pyProc.pid, '/f', '/t']);
    } else {
      pyProc.kill();
    }
  }
});
