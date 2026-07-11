const fs = require("node:fs")
const path = require("node:path")

const baseline = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "lint-baseline.json"), "utf8"))
let input = ""

process.stdin.setEncoding("utf8")
process.stdin.on("data", chunk => { input += chunk })
process.stdin.on("end", () => {
  const reports = JSON.parse(input)
  const current = { errors: 0, warnings: 0, rules: {} }

  for (const report of reports) {
    for (const message of report.messages) {
      const rule = message.ruleId ?? "parse"
      current.rules[rule] = (current.rules[rule] ?? 0) + 1
      if (message.severity === 2) current.errors += 1
      if (message.severity === 1) current.warnings += 1
    }
  }

  const regressions = []
  if (current.errors > baseline.errors) regressions.push(`errors: ${current.errors} > ${baseline.errors}`)
  for (const [rule, count] of Object.entries(current.rules)) {
    if (count > (baseline.rules[rule] ?? 0)) regressions.push(`${rule}: ${count} > ${baseline.rules[rule] ?? 0}`)
  }

  console.log(JSON.stringify(current, null, 2))
  if (regressions.length > 0) {
    console.error(`Lint baseline regression:\n${regressions.join("\n")}`)
    process.exitCode = 1
  }
})
