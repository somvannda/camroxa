import path from "node:path";
import crypto from "node:crypto";
import { promises as fs } from "node:fs";
import { spawn } from "node:child_process";
import { pathExists } from "./fs/pathUtils";

type EnsureVisualizerEnvOptions = {
  basePythonPath: string;
  appPath: string;
  userDataPath: string;
  onStatus?: (message: string) => void;
};

const isWindows = process.platform === "win32";

function venvPythonPath(venvDir: string) {
  return isWindows ? path.join(venvDir, "Scripts", "python.exe") : path.join(venvDir, "bin", "python");
}

function sha256Text(input: string) {
  return crypto.createHash("sha256").update(input, "utf-8").digest("hex");
}

async function runCmd(cmd: string, args: string[], cwd: string) {
  return await new Promise<{ ok: true } | { ok: false; message: string }>((resolve) => {
    const child = spawn(cmd, args, { cwd, windowsHide: true, env: { ...process.env, PYTHONUNBUFFERED: "1" } });
    let stderr = "";
    child.stderr.on("data", (c) => {
      stderr += String(c || "");
    });
    child.on("error", (e) => resolve({ ok: false, message: e instanceof Error ? e.message : "Failed to start process" }));
    child.on("close", (code) => {
      if (code === 0) return resolve({ ok: true });
      const tail = String(stderr || "")
        .trim()
        .split("\n")
        .slice(-10)
        .join("\n");
      resolve({ ok: false, message: tail || `Command failed (exit code ${code ?? "unknown"})` });
    });
  });
}

export async function ensureVisualizerEnv(
  opts: EnsureVisualizerEnvOptions,
): Promise<{ ok: true; pythonPath: string } | { ok: false; message: string }> {
  const basePythonPath = String(opts.basePythonPath || "").trim();
  if (!basePythonPath) return { ok: false, message: "Python executable was not found. Set Python path in Video tab." };

  const requirementsPath = path.join(opts.appPath, "visualizer", "requirements.txt");
  if (!(await pathExists(requirementsPath))) return { ok: false, message: "visualizer/requirements.txt was not found" };

  const requirementsText = await fs.readFile(requirementsPath, "utf-8");
  const requirementsSha = sha256Text(requirementsText);

  const venvDir = path.join(opts.userDataPath, "python", "visualizer");
  const pythonPath = venvPythonPath(venvDir);
  const markerPath = path.join(venvDir, ".mg_env.json");

  const markerRaw = (await pathExists(markerPath)) ? await fs.readFile(markerPath, "utf-8") : "";
  const marker = markerRaw ? (JSON.parse(markerRaw) as any) : null;
  const isReady = (await pathExists(pythonPath)) && marker?.requirementsSha === requirementsSha;
  if (isReady) return { ok: true, pythonPath };

  opts.onStatus?.("Preparing Python environment...");
  await fs.mkdir(venvDir, { recursive: true });

  if (!(await pathExists(pythonPath))) {
    opts.onStatus?.("Creating Python venv...");
    const r = await runCmd(basePythonPath, ["-m", "venv", venvDir], opts.appPath);
    if (r.ok === false) return { ok: false, message: `Failed to create venv: ${r.message}` };
  }

  opts.onStatus?.("Installing visualizer dependencies (first run only)...");
  const pipArgs = ["-m", "pip", "install", "--disable-pip-version-check", "--no-input", "-r", requirementsPath];
  const install = await runCmd(pythonPath, pipArgs, opts.appPath);
  if (install.ok === false) return { ok: false, message: install.message };

  await fs.writeFile(markerPath, JSON.stringify({ requirementsSha, installedAt: new Date().toISOString() }, null, 2), "utf-8");
  return { ok: true, pythonPath };
}

