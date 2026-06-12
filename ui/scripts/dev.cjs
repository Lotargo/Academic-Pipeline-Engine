const { spawn } = require("node:child_process")
const fs = require("node:fs")
const http = require("node:http")
const net = require("node:net")
const path = require("node:path")

const projectRoot = path.join(__dirname, "..")
const nextBin = path.join(projectRoot, "node_modules", "next", "dist", "bin", "next")
const lockPath = path.join(projectRoot, ".next", "dev", "lock")
const args = process.argv.slice(2)
const requestedPort = getRequestedPort(args) || Number(process.env.PORT) || 3000

main().catch((error) => {
  console.error(error?.message || error)
  process.exit(1)
})

async function main() {
  if (fs.existsSync(lockPath)) {
    const runningUrl = await findRunningDevUrl(requestedPort)

    if (runningUrl) {
      console.log(`Next dev is already running for this workspace at ${runningUrl}`)
      console.log("Reusing the existing server instead of starting a second instance.")
      process.exit(0)
    }

    console.error(`Unable to acquire Next dev lock: ${lockPath}`)
    console.error("Another dev server may still be starting, or the lock is stale.")
    console.error("Terminate the existing next dev process, then run npm run dev again.")
    process.exit(1)
  }

  const env = {
    ...process.env,
    BASELINE_BROWSER_MAPPING_IGNORE_OLD_DATA: "true",
    BROWSERSLIST_IGNORE_OLD_DATA: "true",
    NODE_OPTIONS: [process.env.NODE_OPTIONS, "--no-deprecation"].filter(Boolean).join(" "),
  }

  const child = spawn(process.execPath, [nextBin, "dev", ...args], {
    cwd: projectRoot,
    env,
    stdio: ["inherit", "pipe", "pipe"],
  })

  child.stdout.on("data", (chunk) => writeFiltered(process.stdout, chunk))
  child.stderr.on("data", (chunk) => writeFiltered(process.stderr, chunk))
  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal)
      return
    }
    process.exit(code ?? 1)
  })
}

function getRequestedPort(argv) {
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if ((arg === "-p" || arg === "--port") && argv[index + 1]) {
      const parsed = Number(argv[index + 1])
      return Number.isFinite(parsed) ? parsed : null
    }
    if (arg.startsWith("--port=")) {
      const parsed = Number(arg.slice("--port=".length))
      return Number.isFinite(parsed) ? parsed : null
    }
  }
  return null
}

async function findRunningDevUrl(port) {
  const candidates = [port, 3000, 3001, 3002]
  const uniquePorts = [...new Set(candidates.filter((candidate) => Number.isInteger(candidate)))]

  for (const candidate of uniquePorts) {
    if (await isHttpReachable(candidate) || await isPortListening(candidate)) {
      return `http://localhost:${candidate}`
    }
  }

  return null
}

function isPortListening(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: "localhost", port })
    socket.setTimeout(700)
    socket.on("connect", () => {
      socket.destroy()
      resolve(true)
    })
    socket.on("timeout", () => {
      socket.destroy()
      resolve(false)
    })
    socket.on("error", () => resolve(false))
  })
}

function isHttpReachable(port) {
  return new Promise((resolve) => {
    const request = http.get(
      {
        host: "localhost",
        port,
        path: "/",
        timeout: 700,
      },
      (response) => {
        response.resume()
        resolve(true)
      },
    )

    request.on("timeout", () => {
      request.destroy()
      resolve(false)
    })
    request.on("error", () => resolve(false))
  })
}

function writeFiltered(stream, chunk) {
  const output = chunk.toString()
  if (!output) return

  const filtered = output
    .split(/\r?\n/)
    .filter((line) => !line.includes("[baseline-browser-mapping] The data in this module is over two months old."))
    .join("\n")

  if (filtered) {
    stream.write(filtered)
  }
}
