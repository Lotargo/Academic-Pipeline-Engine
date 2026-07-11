const { spawnSync } = require("node:child_process")
const path = require("node:path")

const nextBin = path.join(__dirname, "..", "node_modules", "next", "dist", "bin", "next")

const env = {
  ...process.env,
  BASELINE_BROWSER_MAPPING_IGNORE_OLD_DATA: "true",
  BROWSERSLIST_IGNORE_OLD_DATA: "true",
  NODE_OPTIONS: [process.env.NODE_OPTIONS, "--no-deprecation"].filter(Boolean).join(" "),
}

const result = spawnSync(process.execPath, [nextBin, "build", "--webpack"], {
  cwd: path.join(__dirname, ".."),
  env,
  encoding: "utf8",
  stdio: "pipe",
})

writeFiltered(process.stdout, result.stdout)
writeFiltered(process.stderr, result.stderr)

process.exit(result.status ?? 1)

function writeFiltered(stream, output) {
  if (!output) return

  const filtered = output
    .split(/\r?\n/)
    .filter((line) => !line.includes("[baseline-browser-mapping] The data in this module is over two months old."))
    .join("\n")

  if (filtered.trim()) {
    stream.write(filtered.endsWith("\n") ? filtered : `${filtered}\n`)
  }
}
