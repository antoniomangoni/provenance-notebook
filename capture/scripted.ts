// A provider that needs no model: it replays fixed tool calls, so every rule of capture is
// tested offline. Load it with a second `-e` and `--provider script`.
//
// NOTEBOOK_SCRIPT names a JSON file: an array of turns, each an array of [tool, arguments]. The
// turn played is the number of assistant messages so far; past the last turn the reply is plain
// text, which ends the session. Turn N reports 100 * (N + 1) input tokens and 10 output tokens.
// A string argument may hold {{ref:N}}: the Nth step reference (probe:NAME@sha256:HEX#step-N) in
// the latest tool result, so a scripted agent can cite what project_map showed it.
import { readFileSync } from "node:fs";
import { type AssistantMessage, createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type Call = [string, Record<string, unknown>];

const REF = /(?:[a-z][a-z0-9_-]*\/)?probe:[a-z0-9]+(?:-[a-z0-9]+)*@sha256:[0-9a-f]{64}#step-(?:0|[1-9][0-9]*)/g;

function latestRefs(messages: any[]): string[] {
	const result = [...messages].reverse().find((message) => message.role === "toolResult");
	const text = (result?.content ?? []).map((part: any) => part?.text ?? "").join("\n");
	// A scripted agent cites other trails only: its own trail's steps appear in the map too.
	const own = new RegExp(`(^|/)probe:${(process.env.NOTEBOOK_TRAIL ?? "").split("/").pop()}@`);
	return [...new Set<string>(text.match(REF) ?? [])].filter((ref) => !own.test(ref));
}

function fill(value: unknown, refs: string[]): unknown {
	if (typeof value === "string") return value.replace(/\{\{ref:(\d+)\}\}/g, (kept, n) => refs[Number(n)] ?? kept);
	if (Array.isArray(value)) return value.map((item) => fill(item, refs));
	if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, fill(item, refs)]));
	return value;
}

export default function (pi: ExtensionAPI) {
	const path = process.env.NOTEBOOK_SCRIPT;
	if (!path) throw new Error("NOTEBOOK_SCRIPT names the JSON file of turns to replay");
	const turns: Call[][] = JSON.parse(readFileSync(path, "utf8"));

	function stream(model: any, context: any) {
		const events = createAssistantMessageEventStream();
		const turn = context.messages.filter((message: any) => message.role === "assistant").length;
		const refs = latestRefs(context.messages);
		const calls = (turns[turn] ?? []).map(([name, args]) => [name, fill(args, refs)] as Call);
		// NOTEBOOK_SCRIPT_NO_USAGE=1 replays a provider that reports no usage, which Pi passes on as zeros.
		const input = process.env.NOTEBOOK_SCRIPT_NO_USAGE === "1" ? 0 : 100 * (turn + 1);
		const output = {
			role: "assistant", content: [], api: model.api, provider: model.provider, model: model.id,
			usage: { input, output: input && 10, cacheRead: 0, cacheWrite: 0, totalTokens: input && input + 10,
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
			stopReason: calls.length ? "toolUse" : "stop", timestamp: Date.now(),
		} as AssistantMessage;
		queueMicrotask(() => {
			events.push({ type: "start", partial: output });
			if (!calls.length) {
				output.content.push({ type: "text", text: "done" });
				events.push({ type: "text_start", contentIndex: 0, partial: output });
				events.push({ type: "text_end", contentIndex: 0, content: "done", partial: output });
			}
			calls.forEach(([name, args], index) => {
				const call = { type: "toolCall" as const, id: `call-${turn}-${index}`, name, arguments: args };
				output.content.push(call);
				events.push({ type: "toolcall_start", contentIndex: index, partial: output });
				events.push({ type: "toolcall_end", contentIndex: index, toolCall: call, partial: output });
			});
			events.push({ type: "done", reason: output.stopReason as any, message: output });
			events.end();
		});
		return events;
	}

	pi.registerProvider("script", {
		baseUrl: "http://localhost:1", apiKey: "none", api: "script-api" as any,
		models: [{ id: "scripted-1", name: "Scripted", reasoning: false, input: ["text"],
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 100000, maxTokens: 1000 }],
		streamSimple: stream as any,
	});
}
