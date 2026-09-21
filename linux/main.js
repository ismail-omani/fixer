const { app, BrowserWindow, Menu, shell } = require("electron");
const path = require("path");

const APP_URL = "https://fixer.pythonanywhere.com";
const APP_HOST = "fixer.pythonanywhere.com";

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  let mainWindow = null;

  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  function createWindow() {
    mainWindow = new BrowserWindow({
      width: 1280,
      height: 820,
      minWidth: 820,
      minHeight: 600,
      show: false,
      autoHideMenuBar: true,
      backgroundColor: "#0f172a",
      icon: path.join(__dirname, "icon.png"),
      title: "Fixer",
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });

    mainWindow.once("ready-to-show", () => mainWindow.show());
    mainWindow.on("closed", () => {
      mainWindow = null;
    });

    mainWindow.webContents.session.setDownloadPath(app.getPath("downloads"));

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      if (isExternal(url)) {
        shell.openExternal(url);
      } else {
        mainWindow.loadURL(url);
      }
      return { action: "deny" };
    });

    mainWindow.webContents.on("will-navigate", (event, url) => {
      if (isExternal(url)) {
        event.preventDefault();
        shell.openExternal(url);
      }
    });

    mainWindow.webContents.on("page-title-updated", (event) => {
      event.preventDefault();
      if (mainWindow) mainWindow.setTitle("Fixer");
    });

    mainWindow.loadURL(APP_URL).catch(() => {});
  }

  function isExternal(url) {
    try {
      const host = new URL(url).hostname;
      return host !== APP_HOST;
    } catch (e) {
      return true;
    }
  }

  app.whenReady().then(() => {
    Menu.setApplicationMenu(null);
    createWindow();
  });

  app.on("window-all-closed", () => {
    app.quit();
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}