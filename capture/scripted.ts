// A provider that needs no model: it replays fixed tool calls, so every rule of capture is
// tested offline. Load it with a second `-e` and `--provider script`.
//
// NOTEBOOK_SCRIPT names a JSON file: an array of turns, each an array of [tool, arguments]. The
// turn played is the number of assistant messages so far; past the last turn the reply is plain
// text, which ends the session. Turn N reports 100 * (N + 1) input tokens and 10 output tokens.
import { readFileSync } from "node:fs";
import { type AssistantMessage, createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type Call = [string, Record<string, unknown>];

export default function (pi: ExtensionAPI) {
	const path = process.env.NOTEBOOK_SCRIPT;
	if (!path) throw new Error("NOTEBOOK_SCRIPT names the JSON file of turns to replay");
	const turns: Call[][] = JSON.parse(readFileSync(path, "utf8"));

	function stream(model: any, context: any) {
		const events = createAssistantMessageEventStream();
		const turn = context.messages.filter((message: any) => message.role === "assistant").length;
		const calls = turns[turn] ?? [];
		const input = 100 * (turn + 1);
		const output = {
			role: "assistant", content: [], api: model.api, provider: model.provider, model: model.id,
			usage: { input, output: 10, cacheRead: 0, cacheWrite: 0, totalTokens: input + 10,
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
