import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { platform } from "node:os";
import { resolve } from "node:path";

const args = process.argv.slice(2);
const env = { ...process.env };

function isWsl() {
  if (platform() !== "linux") {
    return false;
  }

  if (env.WSL_DISTRO_NAME || env.WSL_INTEROP) {
    return true;
  }

  try {
    return readFileSync("/proc/version", "utf8").toLowerCase().includes("microsoft");
  } catch {
    return false;
  }
}

const cwd = process.cwd();
const isWindowsMount = /^\/mnt\/[a-z]\//i.test(cwd);

if (!env.CARGO_TARGET_DIR && isWsl() && isWindowsMount) {
  env.CARGO_TARGET_DIR = `${env.HOME}/.cache/ue4ss-mod-manager/target`;
}

const tauriBin = platform() === "win32" ? "tauri.cmd" : "tauri";
const tauriJs = resolve(cwd, "node_modules", "@tauri-apps", "cli", "tauri.js");
const localTauri = resolve(
  cwd,
  "node_modules",
  ".bin",
  tauriBin,
);
const command = existsSync(localTauri) ? localTauri : tauriBin;

const child =
  existsSync(tauriJs)
    ? spawn(process.execPath, [tauriJs, ...args], {
        cwd,
        env,
        shell: false,
        stdio: "inherit",
      })
    : spawn(command, args, {
        cwd,
        env,
        shell: false,
        stdio: "inherit",
      });

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }

  process.exit(code ?? 1);
});
