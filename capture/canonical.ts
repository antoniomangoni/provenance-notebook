// Canonical JSON and digests, byte for byte as trail.py computes them: sorted keys, no
// whitespace, raw non-ASCII. Step files are written by this side and hashed again by Python, so
// the two must agree on every value a step can hold. Keys are ASCII (the schema's patterns make
// them so), which is what keeps JavaScript's and Python's key order the same.
import { createHash, createHmac } from "node:crypto";

// Python writes a non-zero float below 1e-4 in exponent form with at least two exponent digits
// (1e-05); JavaScript writes 0.00001. Everything else already matches once Python has parsed it.
function number(value: number): string {
	if (value !== 0 && Math.abs(value) < 1e-4) return value.toExponential().replace(/e-(\d)$/, "e-0$1");
	return JSON.stringify(value);
}

export function canonical(value: unknown): string {
	if (typeof value === "number") return number(value);
	if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
	if (value && typeof value === "object") {
		const fields = value as Record<string, unknown>;
		return "{" + Object.keys(fields).sort().map((key) => JSON.stringify(key) + ":" + canonical(fields[key])).join(",") + "}";
	}
	return JSON.stringify(value);
}

export function digest(data: string | Uint8Array): string {
	return "sha256:" + createHash("sha256").update(data).digest("hex");
}

// The digest of a non-public value, under the trail's secret, which is kept outside the trail.
export function keyed(key: Uint8Array, data: string | Uint8Array): string {
	return "hmac-sha256:" + createHmac("sha256", key).update(data).digest("hex");
}
