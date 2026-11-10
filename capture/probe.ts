// Throwaway spike: checks the capture plan's assumptions against Pi 0.84.1. Not part of the entry.
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Type } from "typebox";
import { createAssistantMessageEventStream, type AssistantMessage } from "@earendil-works/pi-ai";
import {
	createBashToolDefinition,
	createLocalBashOperations,
	type ExtensionAPI,
	isToolCallEventType,
} from "@earendil-works/pi-coding-agent";

const DIR = process.env.SPIKE_DIR ?? "/tmp/pi-spike-out";
const TRAIL = join(DIR, "trail");
const SCRIPT = process.env.SPIKE_SCRIPT ?? "main";
mkdirSync(join(TRAIL, "steps"), { recursive: true });
const t0 = Date.now();
const log = (ev: string, data: Record<string, unknown> = {}) =>
	appendFileSync(join(DIR, "events.jsonl"), JSON.stringify({ t: Date.now() - t0, ev, ...data }) + "\n");
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// --- canonical JSON as trail.py writes it: sorted keys, no spaces, raw non-ASCII.
export function canonical(value: unknown): string {
	if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
	if (value && typeof value === "object")
		return "{" + Object.keys(value).sort().map((k) => JSON.stringify(k) + ":" + canonical((value as any)[k])).join(",") + "}";
	return JSON.stringify(value);
}
const sha = (s: string | Buffer) => "sha256:" + createHash("sha256").update(s).digest("hex");

// --- one serialised writer: seq and prev are assigned in queue order.
let queue: Promise<unknown> = Promise.resolve();
let steps: any[] = [];
function write(step: Record<string, unknown>): Promise<string> {
	const next = queue.then(async () => {
		const seq = steps.length;
		const full: any = { version: 2, id: `step-${seq}`, seq, trail: "pi-spike", at: new Date().toISOString(), ...step };
		if (seq) full.prev = sha(canonical(steps[seq - 1]));
		writeFileSync(join(TRAIL, "steps", `step-${seq}.json`), JSON.stringify(full, null, 2) + "\n");
		steps.push(full);
		log("wrote", { id: full.id, kind: full.kind });
		return full.id as string;
	});
	queue = next.catch(() => {});
	return next;
}

// --- scripted provider: each turn's tool calls are fixed, chosen by how many assistant turns came before.
type Call = [string, Record<string, unknown>];
const SCRIPTS: Record<string, Call[][]> = {
	main: [
		[["propose_plan", { reasoning: "bad", measure: "auc" }], ["propose_plan", { reasoning: "exit clean", measure: "exit" }]],
		[["bash", { command: "sleep 1; echo slow" }], ["bash", { command: "seq 1 3000" }], ["bash", { command: "echo fail; exit 3" }]],
		[["write", { path: join(TRAIL, "steps", "step-99.json"), content: "{}" }], ["bash", { command: "echo BLOCKME" }], ["bash", { command: "echo THROWME" }]],
		[["bash", { command: "echo TERMINATE" }]],
		[],
	],
	failtrunc: [[["propose_plan", { reasoning: "exit clean", measure: "exit" }], ["bash", { command: "seq 1 3000; exit 1" }]], []],
	crash: [[["propose_plan", { reasoning: "exit clean", measure: "exit" }]], [["bash", { command: "sleep 30" }]], []],
};
function streamScripted(model: any, context: any, options?: any) {
	const stream = createAssistantMessageEventStream();
	const turn = context.messages.filter((m: any) => m.role === "assistant").length;
	const ledger = context.messages.filter((m: any) => JSON.stringify(m).includes("LEDGER")).length;
	log("provider_request", { turn, messages: context.messages.length, ledgerMessages: ledger });
	const calls = SCRIPTS[SCRIPT][turn] ?? [];
	const output: AssistantMessage = {
		role: "assistant", content: [], api: model.api, provider: model.provider, model: model.id,
		usage: { input: 100 * (turn + 1), output: 10, cacheRead: 0, cacheWrite: 0, totalTokens: 100 * (turn + 1) + 10,
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
		stopReason: calls.length ? "toolUse" : "stop", timestamp: Date.now(),
	} as AssistantMessage;
	queueMicrotask(() => {
		stream.push({ type: "start", partial: output });
		if (!calls.length) {
			output.content.push({ type: "text", text: "done" });
			stream.push({ type: "text_start", contentIndex: 0, partial: output });
			stream.push({ type: "text_end", contentIndex: 0, content: "done", partial: output });
		}
		calls.forEach(([name, args], i) => {
			const call = { type: "toolCall" as const, id: `call-${turn}-${i}`, name, arguments: args };
			output.content.push(call);
			stream.push({ type: "toolcall_start", contentIndex: i, partial: output });
			stream.push({ type: "toolcall_end", contentIndex: i, toolCall: call, partial: output });
		});
		stream.push({ type: "done", reason: output.stopReason as any, message: output });
		stream.end();
	});
	return stream;
}

export default function (pi: ExtensionAPI) {
	pi.registerProvider("script", {
		baseUrl: "http://localhost:1", apiKey: "none", api: "script-api" as any,
		models: [{ id: "scripted-1", name: "Scripted", reasoning: false, input: ["text"],
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 100000, maxTokens: 1000 }],
		streamSimple: streamScripted as any,
	});

	const declared = ["exit"];
	let plan = "";
	pi.on("session_start", async (_e, ctx) => {
		log("session_start", { sessionId: ctx.sessionManager.getSessionId(), model: ctx.model?.id, provider: ctx.model?.provider });
		await write({ kind: "task", by: "runner:pi-spike", summary: "Spike task", question: "Does capture work?",
			agent: { name: "pi", version: "0.84.1", model: `${ctx.model?.provider}/${ctx.model?.id}` },
			project: "spike", declared_measures: declared });
	});

	pi.registerTool({
		name: "propose_plan", label: "Propose plan", executionMode: "sequential", description: "State a plan and its expectation before running it",
		parameters: Type.Object({ reasoning: Type.String(), measure: Type.String() }),
		async execute(id, params) {
			log("propose_plan", { id, measure: params.measure });
			if (params.measure !== "exit" && !declared.includes(params.measure))
				throw new Error(`measure ${params.measure} is not declared by the task; declared: ${declared.join(", ")}`);
			plan = await write({ kind: "plan", by: "agent:scripted-1", hook: "pi:propose_plan", summary: "Exit clean",
				reasoning: params.reasoning, expectations: [{ name: "exits-clean", measure: "exit", comparison: "exit_ok" }] });
			return { content: [{ type: "text", text: `recorded as ${plan}` }], details: {} };
		},
	});

	// bash override: the stock tool, with exec wrapped so the exit code is kept per call id.
	const exits = new Map<string, number | null>();
	const runs = new Map<string, string>();
	const local = createLocalBashOperations();
	const stock = createBashToolDefinition(process.cwd());
	pi.registerTool({
		...stock,
		async execute(id, params, signal, onUpdate, ctx) {
			const tool = createBashToolDefinition(ctx.cwd, { operations: { exec: async (command, cwd, options) => {
				log("exec_start", { id });
				const result = await local.exec(command, cwd, options);
				exits.set(id, result.exitCode);
				log("exec_end", { id, exitCode: result.exitCode });
				return result;
			} } });
			return tool.execute(id, params, signal, onUpdate, ctx);
		},
	});

	pi.on("tool_call", async (event) => {
		log("tool_call_start", { id: event.toolCallId, tool: event.toolName });
		await sleep(200); // makes overlapping handlers visible in the log
		if ((isToolCallEventType("write", event) || isToolCallEventType("edit", event)) && event.input.path.startsWith(TRAIL)) {
			log("tool_call_block", { id: event.toolCallId, why: "trail path" });
			return { block: true, reason: "The trail folder is written only by capture" };
		}
		if (isToolCallEventType("bash", event)) {
			const command = event.input.command;
			if (command.includes("BLOCKME")) return { block: true, reason: "blocked by probe" };
			if (command.includes("THROWME")) throw new Error("handler threw");
			if (command.includes("TERMINATE")) return { block: true, reason: "budget spent", terminate: true };
			runs.set(event.toolCallId, await write({ kind: "run", by: "runner:pi-spike", hook: "pi:tool_call", summary: "Run",
				command: { shown: command, digest: sha(command) }, code: { ref: "commit:0000000" },
				links: [{ relation: "implements", target: plan, status: "confirmed" }] }));
		}
		log("tool_call_end", { id: event.toolCallId });
	});

	pi.on("tool_result", async (event) => {
		const details: any = event.details;
		log("tool_result", { id: event.toolCallId, tool: event.toolName, isError: event.isError, exitCode: exits.get(event.toolCallId),
			truncation: details?.truncation ? { truncated: details.truncation.truncated, by: details.truncation.truncatedBy,
				totalLines: details.truncation.totalLines, outputLines: details.truncation.outputLines } : null,
			tail: JSON.stringify(event.content).slice(-80) });
		const run = runs.get(event.toolCallId);
		if (!run) return;
		const code = exits.get(event.toolCallId) ?? -1;
		await write({ kind: "observation", by: "runner:pi-spike", hook: "pi:tool_result", summary: "Observed",
			exit_code: code, outcome: code === 0 ? "as_expected" : "failed",
			checks: [{ expectation: "exits-clean", held: code === 0 }],
			...(code === 0 ? {} : { error: { class: "exit" } }),
			links: [{ relation: "observes", target: run, status: "confirmed" }, { relation: "tests", target: plan, status: "confirmed" }] });
	});

	pi.on("context", async (event) => {
		log("context", { messages: event.messages.length });
		return { messages: [...event.messages, { role: "user", content: [{ type: "text", text: "LEDGER: runs so far " + runs.size }], timestamp: Date.now() }] };
	});
	pi.on("turn_end", async (event) => log("turn_end", { turn: event.turnIndex, usage: (event.message as any)?.usage }));
	pi.on("agent_end", async () => log("agent_end"));
}
