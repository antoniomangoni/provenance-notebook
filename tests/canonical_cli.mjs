// For each JSON value on stdin, one per line: the text JSON.stringify writes into a step file,
// the capture side's canonical form of it, and that form's digest, tab-separated.
import { readFileSync } from "node:fs";
import { canonical, digest } from "../capture/canonical.ts";

for (const line of readFileSync(0, "utf8").split("\n").filter(Boolean)) {
	const value = JSON.parse(line);
	console.log([JSON.stringify(value), canonical(value), digest(canonical(value))].join("\t"));
}
