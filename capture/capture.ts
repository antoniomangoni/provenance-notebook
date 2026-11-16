// Capture: a Pi extension that writes a provenance trail as the agent works.
//
// The agent cannot write the trail. Plans enter only through the propose_plan tool; a run is
// written before its command executes and its observation after, by hooks around the agent; and
// measures are read from the metrics file the command wrote, never from what the agent says.
//
// The file has three layers. The step builders take plain data and know nothing of Pi, so an
// adapter for another host is new wiring. The Trail writes steps one at a time. The default
// export gathers data from Pi's hooks and calls the two.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, resolve, sep } from "node:path";
import { Type } from "typebox";
import { createBashToolDefinition, createLocalBashOperations, type ExtensionAPI, isToolCallEventType, VERSION } from "@earendil-works/pi-coding-agent";
import { canonical, digest } from "./canonical.ts";

export type Step = Record<string, any>;
export type Expectation = { name: string; measure: string; comparison: string; threshold?: number };
export type Task = {
	summary: string; question: string; project: string; declared_measures: string[];
	public_parameters: string[]; inputs: string[]; by: string; builds_on?: string[];
};

export const RUNNER = "runner:notebook/0.1";
const EXIT = ["exit_ok", "exit_fail"];
const SIGNS: Record<string, string> = { lt: "<", le: "<=", eq: "==", ge: ">=", gt: ">" };
const TRAIL_NAME = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const MEASURE = /^[A-Za-z0-9_.-]{1,100}$/;
const METRICS = "out/metrics.json";
// Another probe's step, pinned at a head: the form the step schema gives a cross-probe link target.
const PROBE_REF = /^([a-z][a-z0-9_-]*\/)?probe:[a-z0-9]+(-[a-z0-9]+)*@sha256:[0-9a-f]{64}(#step-(0|[1-9][0-9]*))?$/;

// The first `length` characters, counted as the schema counts them, so a cut never splits one.
function clip(text: string, length: number): string {
	return Array.from(text).slice(0, length).join("");
}

// What capture tells the agent when it will not record something. It never holds a parameter's value.
export class Refusal extends Error {}

// ---------------------------------------------------------------------------------------------
// Step builders: plain data in, a step out.

export function readTask(text: string): Task {
	const task = JSON.parse(text);
	for (const field of ["summary", "question", "project", "by"])
		if (typeof task[field] !== "string" || !task[field]) throw new Error(`the task file needs ${field}`);
	for (const field of ["declared_measures", "public_parameters", "inputs"])
		if (!Array.isArray(task[field]) || task[field].some((item: unknown) => typeof item !== "string"))
			throw new Error(`the task file needs ${field}, a list of strings`);
	// An input is cited as file:PATH, which has no room for a space, an @ or a #.
	if (task.inputs.some((path: string) => !/^[^\s@#]+$/.test(path))) throw new Error("the task file's inputs are paths without spaces, @ or #");
	// Step 0 is written from these, so what the step schema would refuse is refused here, before
	// a session is spent on a trail that could not pass the checker.
	const fits: [string, boolean][] = [
		["summary of at most 200 characters", Array.from(task.summary).length <= 200],
		["question of at most 2,000 characters", Array.from(task.question).length <= 2000],
		["project of lower-case letters, digits, _ and -", /^[a-z][a-z0-9_-]{0,99}$/.test(task.project)],
		["by as human:NAME or runner:NAME", /^(human|runner):[A-Za-z0-9._/@-]{1,100}$/.test(task.by)],
		["declared_measures, at least one, of letters, digits, _ . and -", task.declared_measures.length > 0 && task.declared_measures.every((name: string) => MEASURE.test(name))],
		["public_parameters of letters, digits, _ . and -", task.public_parameters.every((name: string) => MEASURE.test(name))],
	];
	for (const [rule, ok] of fits) if (!ok) throw new Error(`the task file needs ${rule}`);
	// The probes this task starts from, as a research map's brief cites them. Optional.
	if (task.builds_on !== undefined && (!Array.isArray(task.builds_on) || task.builds_on.some((ref: unknown) => typeof ref !== "string" || !PROBE_REF.test(ref))))
		throw new Error("the task file needs builds_on as a list of probe references pinned at a head, PROJECT/probe:TRAIL@sha256:HEX#step-N");
	return task;
}

// The actor of the agent's steps: the model's id, with whatever the schema's pattern refuses replaced.
export function agentName(model: string): string {
	return "agent:" + `pi/${model}`.replace(/[^A-Za-z0-9._/@-]/g, "-").slice(0, 100);
}

export function taskStep(task: Task, version: string, model: string): Step {
	return {
		kind: "task", by: task.by, hook: "pi:session_start", summary: task.summary, question: task.question, project: task.project,
		agent: { name: "pi", version, model }, declared_measures: task.declared_measures, public_parameters: task.public_parameters,
		...(task.builds_on?.length ? { links: task.builds_on.map((target) => ({ relation: "builds_on", target, status: "confirmed" })) } : {}),
	};
}

// An expectation's name as the schema spells it: lower case, words joined by single hyphens.
export function slug(name: string): string {
	return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function known(steps: Step[]): string {
	const plans = steps.filter((step) => step.kind === "plan").map((step) => step.id);
	const observations = steps.filter((step) => step.kind === "observation").map((step) => `${step.id} (${step.outcome})`);
	return `Plans: ${plans.join(", ") || "none"}. Observations: ${observations.join(", ") || "none"}.`;
}

export type PlanInput = {
	summary: string; reasoning: string; expectations: Expectation[]; supersedes?: string; triggered_by?: string; builds_on?: string[];
};

// The agent's plan as a step, or a Refusal that says what can be used instead. Nothing the agent
// wrote is shortened or corrected: a plan that does not fit is refused, and the agent writes it again.
export function planStep(input: PlanInput, task: Task, steps: Step[], by: string, citable: Set<string> = new Set()): Step {
	if (!input.summary || input.summary.length > 200) throw new Refusal("summary is 1 to 200 characters; the plan was not recorded");
	if (!input.reasoning || input.reasoning.length > 8000) throw new Refusal("reasoning is 1 to 8,000 characters; the plan was not recorded");
	if (!Array.isArray(input.expectations) || !input.expectations.length)
		throw new Refusal("a plan states at least one expectation before it is run; the plan was not recorded");
	const declared = `The task declares: ${task.declared_measures.join(", ")}. A plan that only looks around has one expectation, exit_ok on measure exit.`;
	const expectations: Expectation[] = [];
	for (const given of input.expectations) {
		const name = slug(String(given.name ?? ""));
		if (!name || name.length > 100) throw new Refusal("each expectation needs a name of letters and digits; the plan was not recorded");
		if (expectations.some((kept) => kept.name === name)) throw new Refusal(`two expectations are named ${name}; the plan was not recorded`);
		if (EXIT.includes(given.comparison)) {
			// An exit expectation measures nothing the task declares, so its measure is always `exit`.
			expectations.push({ name, measure: "exit", comparison: given.comparison });
			continue;
		}
		if (!(given.comparison in SIGNS))
			throw new Refusal(`expectation ${name}: comparison is one of lt, le, eq, ge, gt, exit_ok, exit_fail; the plan was not recorded`);
		if (!task.declared_measures.includes(given.measure))
			throw new Refusal(`expectation ${name} measures something the task does not declare. ${declared} The plan was not recorded`);
		if (typeof given.threshold !== "number" || !Number.isFinite(given.threshold))
			throw new Refusal(`expectation ${name} has no threshold to compare against; the plan was not recorded`);
		expectations.push({ name, measure: given.measure, comparison: given.comparison, threshold: given.threshold });
	}
	const step: Step = { kind: "plan", by, hook: "pi:propose_plan", summary: input.summary, reasoning: input.reasoning, expectations };
	// A sibling's step this plan builds on: only a reference project_map showed, so its head is one the
	// sibling had. The link is the agent's, so it is suggested, as the checker requires.
	const cited = input.builds_on ?? [];
	if (!Array.isArray(cited) || cited.some((ref) => typeof ref !== "string" || !citable.has(ref)))
		throw new Refusal("builds_on lists step references exactly as project_map showed them in this session, such as "
			+ "probe:NAME@sha256:HEX#step-N; the plan was not recorded");
	const builds = [...new Set(cited)].map((target) => ({ relation: "builds_on", target, status: "suggested" }));
	if (builds.length) step.links = builds;
	if (!input.supersedes && !input.triggered_by) return step;
	// A plan that replaces another names the observation that made it, and the other way round.
	const old = steps.find((kept) => kept.id === input.supersedes);
	const trigger = steps.find((kept) => kept.id === input.triggered_by);
	if (!input.supersedes || !input.triggered_by)
		throw new Refusal(`supersedes and triggered_by go together: the plan replaced and the observation that contradicted it. ${known(steps)} The plan was not recorded`);
	if (old?.kind !== "plan") throw new Refusal(`supersedes names a plan of this trail by its id. ${known(steps)} The plan was not recorded`);
	if (trigger?.kind !== "observation")
		throw new Refusal(`triggered_by names an observation of this trail by its id. ${known(steps)} The plan was not recorded`);
	step.links = [
		{ relation: "supersedes", target: old.id, status: "suggested" },
		{ relation: "triggered_by", target: trigger.id, status: "suggested" },
		...builds,
	];
	return step;
}

// The public parameters of a command: each `--name value` or `--name=value` whose name the task
// lists. A flag spelt with hyphens matches a name spelt with underscores. Nothing else is kept:
// a value the task did not make public is not recorded at all.
export function parameters(command: string, names: string[]): Step[] {
	const tokens = (command.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) ?? []).map((token) => token.replace(/["']/g, ""));
	const found: Step[] = [];
	tokens.forEach((token, at) => {
		if (!token.startsWith("--")) return;
		const [flag, ...rest] = token.slice(2).split("=");
		const name = names.find((known) => known === flag || known === flag.replace(/-/g, "_"));
		const next = tokens[at + 1];
		const value = rest.length ? rest.join("=") : next !== undefined && !next.startsWith("--") && !/^[;&|<>]/.test(next) ? next : undefined;
		if (name && value !== undefined && Array.from(value).length <= 500) found.push({ name, digest: digest(value), value });
	});
	return found;
}

// ---------------------------------------------------------------------------------------------
// Tracing: which files a command opened. strace follows the command and every process it starts;
// -y prints the path each successful open returned, so a relative path is already resolved.

const OPENED = /^\d+\s+(?:open|openat|openat2)\((.*)\)\s+=\s+\d+<(.+)>$/;
const UNTRACKED = [".git", ".venv", "__pycache__"];

function quote(text: string): string {
	return "'" + text.replace(/'/g, "'\\''") + "'";
}

// strace on PATH, unless NOTEBOOK_TRACE is 0; null means commands run untraced and their observations have no reads.
export function tracer(env: NodeJS.ProcessEnv = process.env): string | null {
	if (env.NOTEBOOK_TRACE === "0") return null;
	for (const dir of (env.PATH ?? "").split(":")) if (dir && existsSync(join(dir, "strace"))) return join(dir, "strace");
	return null;
}

export function tracedCommand(command: string, strace: string, trace: string, wrap: string[] = []): string {
	return `${quote(strace)} -f -qq -y -e trace=open,openat,openat2 -e status=successful -o ${quote(trace)} -- ${sandboxedCommand(command, wrap)}`;
}

// The command as bash runs it, inside the sandbox's bwrap when there is one.
export function sandboxedCommand(command: string, wrap: string[] = []): string {
	return [...wrap, "bash", "-c", command].map(quote).join(" ");
}

// The sandbox (spec 8): with NOTEBOOK_SANDBOX=1 each command runs in bwrap, so what project_map withholds
// cannot be read from disk instead. The filesystem is read-only; the repository (with the map, the briefs
// and every output), the trails, the store, the map, the directory the workspaces share and Pi's
// configuration are hidden under empty tmpfs; the workspace and uv's cache are bound back writable.
export type Sandbox = { bwrap: string; hidden: string[]; writable: string[]; workspace: string };

function onPath(name: string, env: NodeJS.ProcessEnv): string | null {
	for (const dir of (env.PATH ?? "").split(":")) if (dir && existsSync(join(dir, name))) return join(dir, name);
	return null;
}

function inside(path: string, root: string): boolean {
	return path === root || path.startsWith(root.endsWith(sep) ? root : root + sep);
}

export function sandboxFor(config: Config, workspace: string, env: NodeJS.ProcessEnv = process.env): Sandbox | null {
	if (!config.sandbox) return null;
	const bwrap = onPath("bwrap", env);
	if (!bwrap) throw new Error("NOTEBOOK_SANDBOX=1 needs bwrap on PATH; nothing runs unsandboxed when a sandbox was asked for");
	const home = realpathSync(env.HOME ?? homedir()), own = realpathSync(workspace);
	const wanted = [config.repo, dirname(config.trail), config.store, config.map, dirname(own), join(home, ".pi"), env.PI_CODING_AGENT_DIR]
		.filter((path): path is string => !!path && existsSync(path)).map((path) => realpathSync(path));
	for (const path of wanted) {
		if (path === "/" || inside(home, path)) throw new Error(`the sandbox would hide ${path}, which holds the home directory`);
		if (inside(own, path) && path !== dirname(own)) throw new Error(`the sandbox would hide ${path}, which holds the workspace`);
	}
	// Outermost first; a path inside one already hidden is hidden with it.
	const hidden: string[] = [];
	for (const path of [...new Set(wanted)].sort((a, b) => a.length - b.length)) if (!hidden.some((root) => inside(path, root))) hidden.push(path);
	const cache = resolve(env.UV_CACHE_DIR ?? join(home, ".cache", "uv"));
	const writable = existsSync(cache) && !hidden.some((root) => inside(cache, root)) ? [realpathSync(cache)] : [];
	return { bwrap, hidden, writable, workspace: own };
}

export function sandboxArgs(box: Sandbox): string[] {
	return [
		box.bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
		...box.hidden.flatMap((path) => ["--tmpfs", path]),
		...box.writable.flatMap((path) => ["--bind", path, path]),
		"--bind", box.workspace, box.workspace, "--die-with-parent", "--",
	];
}

// The workspace files a trace shows opened for reading, workspace-relative, sorted, at their digest now.
export function readsOf(trace: string, workspace: string): Step[] {
	const root = realpathSync(workspace);
	const found = new Set<string>();
	for (const line of trace.split("\n")) {
		const opened = OPENED.exec(line);
		if (!opened || opened[1].includes("O_WRONLY") || opened[1].includes("O_DIRECTORY")) continue;
		const path = opened[2];
		if (!path.startsWith(root + sep)) continue;
		const relative = path.slice(root.length + 1);
		if (relative.split(sep).some((part) => UNTRACKED.includes(part))) continue;
		try {
			if (statSync(path).isFile()) found.add(relative);
		} catch {
			// Opened, then removed before the command ended: there is no content to cite.
		}
	}
	return [...found].sort().slice(0, 500).map((relative) => ({ ref: `file:${relative}`, digest: digest(readFileSync(join(root, relative))) }));
}

// The runner's intent, written before the command executes.
export function runStep(command: string, commit: string, environment: string | undefined, kept: Step[], inputs: Step[], plan: Step): Step {
	return {
		kind: "run", by: RUNNER, hook: "pi:tool_call", summary: clip(command.replace(/\s+/g, " ").trim(), 200),
		command: { shown: clip(command, 2000), digest: digest(command) }, code: { ref: `commit:${commit}` },
		...(environment ? { environment } : {}), parameters: kept, inputs,
		links: [{ relation: "implements", target: plan.id, status: "confirmed" }],
	};
}

// The measures in a metrics file: one non-empty object of measure names to finite numbers, or
// null for anything else. A number that JavaScript and Python would read differently is refused
// too, since the checker reads the stored file again and must find the step's measures in it.
export function readMetrics(bytes: Uint8Array): Record<string, number> | null {
	const text = Buffer.from(bytes).toString("utf8");
	if (!Buffer.from(text, "utf8").equals(Buffer.from(bytes))) return null;
	let value: unknown;
	try {
		value = JSON.parse(text);
	} catch {
		return null;
	}
	if (!value || typeof value !== "object" || Array.isArray(value)) return null;
	const entries = Object.entries(value);
	if (!entries.length || entries.length > 200) return null;
	for (const [name, measured] of entries) {
		if (!MEASURE.test(name) || typeof measured !== "number" || !Number.isFinite(measured)) return null;
		if (Number.isInteger(measured) && !Number.isSafeInteger(measured)) return null;
	}
	return value as Record<string, number>;
}

function holds(expectation: Expectation, measured: number): boolean {
	const threshold = expectation.threshold!;
	return { lt: measured < threshold, le: measured <= threshold, eq: measured === threshold, ge: measured >= threshold, gt: measured > threshold }[
		expectation.comparison as "lt"
	];
}

export type Metrics = { digest: string; measures: Record<string, number> };

// The runner's observation of a finished run. Checks and outcome follow trail.check_observation
// exactly, because the checker recomputes both: a check for each expectation whose measure is
// there, `failed` for a non-zero exit nobody expected, `inconclusive` when a check is missing.
export function observationStep(run: Step, plan: Step, exitCode: number, durationMs: number, metrics: Metrics | null, reads?: Step[]): Step {
	const measures = metrics?.measures ?? {};
	const expectations: Expectation[] = plan.expectations;
	const checks: Step[] = [];
	for (const expectation of expectations) {
		if (EXIT.includes(expectation.comparison))
			checks.push({ expectation: expectation.name, held: (expectation.comparison === "exit_ok") === (exitCode === 0) });
		else if (expectation.measure in measures)
			checks.push({ expectation: expectation.name, measured: measures[expectation.measure], held: holds(expectation, measures[expectation.measure]) });
	}
	let outcome: string;
	if (exitCode !== 0 && !expectations.some((expectation) => expectation.comparison === "exit_fail")) outcome = "failed";
	else if (checks.length < expectations.length) outcome = "inconclusive";
	else outcome = checks.every((check) => check.held) ? "as_expected" : "contradicted";
	const source = metrics ? { ref: `file:${METRICS}`, digest: metrics.digest } : undefined;
	const step: Step = {
		kind: "observation", by: RUNNER, hook: "pi:tool_result", summary: "", exit_code: exitCode, duration_ms: Math.max(0, Math.round(durationMs)),
		...(source ? { outputs: [source], measures_source: source, measures: Object.entries(measures).map(([name, value]) => ({ name, value })) } : {}),
		...(reads ? { reads } : {}),
		checks, outcome, ...(outcome === "failed" ? { error: { class: "exit" } } : {}),
		links: [
			{ relation: "observes", target: run.id, status: "confirmed" },
			{ relation: "tests", target: plan.id, status: "confirmed" },
		],
	};
	const detail = missed(step, plan);
	step.summary = clip(outcome.replace("_", " ") + (detail ? `: ${detail}` : ""), 200);
	return step;
}

// What an observation shows against its plan, in the words the receipt and the summary share:
// the exit code of a failed run, each expectation that did not hold, each that could not be checked.
export function missed(observation: Step, plan: Step): string {
	const expectations: Expectation[] = plan.expectations;
	const parts: string[] = observation.outcome === "failed" ? [`exit code ${observation.exit_code}`] : [];
	for (const check of observation.checks as Step[]) {
		const expectation = expectations.find((kept) => kept.name === check.expectation)!;
		if (check.held) continue;
		if (!EXIT.includes(expectation.comparison))
			parts.push(`${expectation.measure} ${check.measured}, expected ${SIGNS[expectation.comparison]} ${expectation.threshold}`);
		else if (observation.outcome !== "failed") parts.push(`exit code ${observation.exit_code}, expected ${expectation.comparison}`);
	}
	const unchecked = expectations.filter((kept) => !observation.checks.some((check: Step) => check.expectation === kept.name));
	if (unchecked.length) parts.push(`no fresh ${METRICS} with ${[...new Set(unchecked.map((kept) => kept.measure))].join(", ")}`);
	return parts.join("; ");
}

// The line the agent reads at the end of a command's result. Its ids are how the agent names an
// observation in triggered_by. It holds measures and thresholds, never a parameter's value.
export function receipt(run: Step, observation: Step, plan: Step): string {
	const detail = missed(observation, plan);
	return `[notebook] run ${run.id}, observation ${observation.id}: ${observation.outcome}` + (detail ? ` (${detail})` : "");
}

export function noteStep(about: Step, hook: string, summary: string, text: string): Step {
	return { kind: "note", by: RUNNER, hook, summary: clip(summary, 200), text, links: [{ relation: "about", target: about.id, status: "confirmed" }] };
}

// ---------------------------------------------------------------------------------------------
// The workspace: code snapshots and the metrics file.

function git(cwd: string, args: string[], env: Record<string, string> = {}): string {
	return execFileSync("git", args, { cwd, env: { ...process.env, ...env }, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

const IDENTITY = {
	GIT_AUTHOR_NAME: "notebook", GIT_AUTHOR_EMAIL: "notebook@localhost", GIT_COMMITTER_NAME: "notebook", GIT_COMMITTER_EMAIL: "notebook@localhost",
};

// The commit that holds the working tree as it is now, on the trail's own branch. The tree is
// staged in an index of its own, so HEAD, the real index and the working tree are not touched.
// Code that did not change since the last snapshot is cited at that snapshot again.
export function snapshot(cwd: string, trail: string, previous: string | undefined): string {
	const scratch = mkdtempSync(join(tmpdir(), "notebook-index-"));
	try {
		const index = { GIT_INDEX_FILE: join(scratch, "index") };
		git(cwd, ["add", "-A"], index);
		const tree = git(cwd, ["write-tree"], index);
		if (previous && git(cwd, ["rev-parse", `${previous}^{tree}`]) === tree) return previous;
		const commit = git(cwd, ["commit-tree", tree, ...(previous ? ["-p", previous] : []), "-m", "The code as a run started"], IDENTITY);
		git(cwd, ["update-ref", `refs/heads/notebook/${trail}`, commit]);
		return commit;
	} finally {
		rmSync(scratch, { recursive: true, force: true });
	}
}

type Stamp = { exists: boolean; modified: bigint };

function stamp(path: string): Stamp {
	const stat = statSync(path, { bigint: true, throwIfNoEntry: false });
	return { exists: !!stat?.isFile(), modified: stat?.mtimeNs ?? 0n };
}

// A path as the file system resolves it, for a file that may not exist yet.
function real(path: string): string {
	let existing = resolve(path);
	const rest: string[] = [];
	while (!existsSync(existing) && dirname(existing) !== existing) {
		rest.unshift(basename(existing));
		existing = dirname(existing);
	}
	return join(realpathSync(existing), ...rest);
}

// ---------------------------------------------------------------------------------------------
// The trail: steps are written through one queue, so seq and prev follow write order.

export class Trail {
	readonly steps: Step[] = [];
	readonly name: string;
	private queue: Promise<unknown> = Promise.resolve();

	constructor(readonly directory: string) {
		this.name = basename(directory);
	}

	write(step: Step): Promise<Step> {
		const next = this.queue.then(() => {
			const seq = this.steps.length;
			const last = this.steps[seq - 1];
			// The capture clock only moves forward, even if the machine's steps back.
			const now = new Date().toISOString();
			const full: Step = { version: 2, id: `step-${seq}`, seq, trail: this.name, at: last && last.at > now ? last.at : now, ...step };
			if (last) full.prev = digest(canonical(last));
			mkdirSync(join(this.directory, "steps"), { recursive: true });
			// `wx` fails on a file that exists: a step is written once.
			writeFileSync(join(this.directory, "steps", `${full.id}.json`), JSON.stringify(full, null, 2) + "\n", { flag: "wx" });
			this.steps.push(full);
			return full;
		});
		this.queue = next.catch(() => {});
		return next;
	}

	latest(kind: string): Step | undefined {
		return this.steps.findLast((step) => step.kind === kind);
	}
}

// ---------------------------------------------------------------------------------------------
// Configuration, from the environment. A missing or wrong value fails at load.

export type Config = {
	task: string; trail: string; store: string; maxRuns: number; maxTokens: number; sandbox: boolean; map?: string; repo?: string;
};

function positive(env: NodeJS.ProcessEnv, name: string, fallback: number): number {
	const value = env[name];
	if (value === undefined || value === "") return fallback;
	if (!/^[1-9][0-9]*$/.test(value)) throw new Error(`${name} is a positive integer`);
	return Number(value);
}

export function configure(env: NodeJS.ProcessEnv): Config {
	for (const name of ["NOTEBOOK_TASK", "NOTEBOOK_TRAIL", "NOTEBOOK_STORE"]) if (!env[name]) throw new Error(`capture needs ${name}`);
	const config = {
		task: resolve(env.NOTEBOOK_TASK!), trail: resolve(env.NOTEBOOK_TRAIL!), store: resolve(env.NOTEBOOK_STORE!),
		maxRuns: positive(env, "NOTEBOOK_MAX_RUNS", 40), maxTokens: positive(env, "NOTEBOOK_MAX_TOKENS", 2_000_000),
		sandbox: env.NOTEBOOK_SANDBOX === "1",
	};
	if (![undefined, "", "0", "1"].includes(env.NOTEBOOK_SANDBOX)) throw new Error("NOTEBOOK_SANDBOX is 1 (commands run in bwrap) or 0");
	if (config.sandbox && !onPath("bwrap", env)) throw new Error("NOTEBOOK_SANDBOX=1 needs bwrap on PATH; nothing runs unsandboxed when a sandbox was asked for");
	if (!existsSync(config.task) || !statSync(config.task).isFile()) throw new Error("NOTEBOOK_TASK is not a file");
	const name = basename(config.trail);
	if (!TRAIL_NAME.test(name) || name.length > 100)
		throw new Error("NOTEBOOK_TRAIL ends in the trail's name: lower-case letters, digits and single hyphens");
	if (existsSync(join(config.trail, "steps"))) throw new Error("NOTEBOOK_TRAIL already holds steps; a trail is written once");
	// A research map the agent may read, with the repository whose project.py reads it. Both or neither.
	if (!env.NOTEBOOK_MAP !== !env.NOTEBOOK_REPO) throw new Error("NOTEBOOK_MAP and NOTEBOOK_REPO go together");
	if (env.NOTEBOOK_MAP) {
		const map = resolve(env.NOTEBOOK_MAP), repo = resolve(env.NOTEBOOK_REPO!);
		if (!existsSync(join(map, "rev-0.json"))) throw new Error("NOTEBOOK_MAP is not a research map: it has no rev-0.json");
		if (!existsSync(join(repo, "project.py"))) throw new Error("NOTEBOOK_REPO has no project.py");
		return { ...config, map, repo };
	}
	return config;
}

// ---------------------------------------------------------------------------------------------
// Pi wiring.

const EXPECTATION = Type.Object({
	name: Type.String({ description: "A short name, such as auc-floor" }),
	measure: Type.String({ description: "A measure the task declares, or exit" }),
	comparison: Type.String({ description: "lt, le, eq, ge or gt against the threshold; exit_ok or exit_fail for the command's exit" }),
	threshold: Type.Optional(Type.Number()),
});
const PLAN = Type.Object({
	summary: Type.String({ description: "One line, at most 200 characters" }),
	reasoning: Type.String({ description: "Why this plan, and what the expectations rest on" }),
	expectations: Type.Array(EXPECTATION, { description: "What the next commands must show, fixed before they run" }),
	supersedes: Type.Optional(Type.String({ description: "The id of the plan this one replaces, such as step-1" })),
	triggered_by: Type.Optional(Type.String({ description: "The id of the observation that contradicted that plan, such as step-3" })),
	builds_on: Type.Optional(Type.Array(Type.String(), {
		description: "Steps of other agents' trails this plan uses, each copied whole from project_map, such as probe:NAME@sha256:HEX#step-N",
	})),
});
// Step references as project_map prints them: another trail's step, pinned at its present head.
const SHOWN_REF = /(?:[a-z][a-z0-9_-]*\/)?probe:[a-z0-9]+(?:-[a-z0-9]+)*@sha256:[0-9a-f]{64}#step-(?:0|[1-9][0-9]*)/g;
const NO_PLAN = "No plan is recorded yet, so this command was not run. Call propose_plan first. "
	+ "To look around before committing to numbers, propose a plan whose only expectation is exit_ok on measure exit.";
const NOT_STARTED = "Capture did not start, so nothing can be recorded and nothing is run.";

export default function (pi: ExtensionAPI) {
	const config = configure(process.env);
	const task = readTask(readFileSync(config.task, "utf8"));
	const trail = new Trail(config.trail);
	let agent = agentName("unknown");
	let code: string | undefined;
	let tokens = 0;
	let stopped = false;
	// What is known of a command between its tool_call and its tool_result, by call id.
	type Pending = {
		run: Step; plan: Step; cwd: string; before: Stamp; started: number; exitCode?: number | null; ended?: number; fresh?: Uint8Array | null;
		trace?: string; reads?: Step[];
	};
	const strace = tracer();
	let box: Sandbox | null = null;
	const pending = new Map<string, Pending>();
	// Every sibling step reference project_map has shown in this session: what a plan may build on.
	const citable = new Set<string>();
	// How many observations the other trails of this project had when the agent last read the map.
	let seenAtRead = 0;
	function siblingObservations(): number {
		const root = dirname(config.trail);
		let count = 0;
		for (const name of existsSync(root) ? readdirSync(root) : []) {
			const steps = join(root, name, "steps");
			if (name === trail.name || !existsSync(join(steps, "step-0.json"))) continue;
			try {
				if (JSON.parse(readFileSync(join(steps, "step-0.json"), "utf8")).project !== task.project) continue;
				for (const file of readdirSync(steps)) {
					try {
						if (JSON.parse(readFileSync(join(steps, file), "utf8")).kind === "observation") count++;
					} catch { /* a step being written: counted next time */ }
				}
			} catch { /* not a trail */ }
		}
		return count;
	}

	pi.on("session_start", async (_event, ctx) => {
		if (trail.steps.length) return;
		// Runs cite snapshots of the code, so the workspace has to be a repository.
		if (git(ctx.cwd, ["rev-parse", "--is-inside-work-tree"]) !== "true") throw new Error("the workspace is not a git repository");
		agent = agentName(ctx.model?.id ?? "unknown");
		box = sandboxFor(config, ctx.cwd);
		const first = await trail.write(taskStep(task, VERSION, `${ctx.model?.provider ?? "unknown"}/${ctx.model?.id ?? "unknown"}`));
		if (box) await trail.write(noteStep(first, "pi:session_start", "Commands run in a sandbox that hides the map and the other trails",
			`Every command runs in bwrap: the filesystem is read-only except the workspace${box.writable.length ? " and uv's cache" : ""}, `
			+ `and these are hidden under empty tmpfs: ${box.hidden.join(", ")}. The project_map tool runs outside the sandbox.`));
	});

	// A model can loop, and a loop is paid for; past a ceiling nothing more runs. The note is written once.
	async function ceiling(): Promise<string | null> {
		const runs = trail.steps.filter((step) => step.kind === "run").length;
		const reached = runs >= config.maxRuns ? `${runs} of at most ${config.maxRuns} runs`
			: tokens >= config.maxTokens ? `${tokens} of at most ${config.maxTokens} tokens` : null;
		if (!reached) return null;
		const reason = `The session reached a ceiling: ${reached}. Nothing more is run.`;
		if (!stopped) {
			stopped = true;
			await trail.write(noteStep(trail.steps[0], "pi:tool_call", `Stopped at a ceiling: ${reached}`, reason));
		}
		return reason;
	}

	pi.on("turn_end", async (event) => {
		const usage = (event.message as any)?.usage ?? {};
		for (const part of ["input", "output", "cacheRead", "cacheWrite"]) if (Number.isFinite(usage[part])) tokens += usage[part];
	});

	pi.registerTool({
		name: "propose_plan", label: "Propose plan", executionMode: "sequential", parameters: PLAN,
		description: "Record a plan and what you expect of it before running anything. Commands run under the most recent plan. "
			+ "To replace a plan that an observation contradicted, give supersedes and triggered_by.",
		async execute(_id, params) {
			if (!trail.steps.length) throw new Refusal(NOT_STARTED);
			const over = await ceiling();
			if (over) throw new Refusal(over);
			const step = await trail.write(planStep(params as PlanInput, task, trail.steps, agent, citable));
			// An agent that has not read the map since its siblings found something is told so: the prompt
			// asks it to read the map before each plan, and a model forgets.
			let text = `recorded as ${step.id}`;
			if (config.map) {
				const fresh = siblingObservations() - seenAtRead;
				if (fresh > 0) text += `\n[notebook] Other agents' trails have ${fresh} new observation${fresh === 1 ? "" : "s"} since you last `
					+ "read the project map. Call project_map before your next plan, and build on what serves your route.";
			}
			return { content: [{ type: "text", text }], details: {} };
		},
	});

	// The research map, read live: what the map and the other agents' trails show now. Each read is a
	// note naming the revision and every sibling head it showed, so the trail records what the agent saw.
	if (config.map) pi.registerTool({
		name: "project_map", label: "Project map", executionMode: "sequential", parameters: Type.Object({}),
		description: "Read the research map this task belongs to, as it stands now: its goals, routes and milestones, what reached each, "
			+ "and what the other agents' trails have found so far, each step pinned at its trail's present head. Numbers from a run that "
			+ "opened a sealed input are withheld. To use another agent's step, copy its reference whole into propose_plan's builds_on.",
		async execute() {
			if (!trail.steps.length) throw new Refusal(NOT_STARTED);
			const over = await ceiling();
			if (over) throw new Refusal(over);
			// project.py runs with no more of the environment than it needs: never the model's key.
			const env = Object.fromEntries(["PATH", "HOME", "TMPDIR"].filter((name) => process.env[name]).map((name) => [name, process.env[name]!]));
			let text: string;
			try {
				text = execFileSync("uv", ["run", "--quiet", "--project", config.repo!, "python", join(config.repo!, "project.py"), "status", config.map!,
					"--live", dirname(config.trail), "--for", trail.name], { cwd: config.repo, env, encoding: "utf8", timeout: 60_000, stdio: ["ignore", "pipe", "pipe"] });
			} catch (error: any) {
				throw new Refusal(`The project map could not be read: ${clip(String(error?.stderr || error?.message || error), 500)}`);
			}
			seenAtRead = siblingObservations();
			const own = new RegExp(`(^|/)probe:${trail.name}@`);
			const refs = [...new Set(text.match(SHOWN_REF) ?? [])].filter((ref) => !own.test(ref));
			for (const ref of refs) citable.add(ref);
			const heads = [...new Set(refs.map((ref) => ref.split("#")[0]))];
			const rev = /map revision (\d+) \((sha256:[0-9a-f]{64})/.exec(text.split("\n")[0]);
			await trail.write({
				kind: "note", by: RUNNER, hook: "pi:project_map",
				summary: clip(`Read the project map at revision ${rev?.[1] ?? "unknown"}, with ${heads.length} other trail heads`, 200),
				text: clip(`project_map showed map revision ${rev?.[1] ?? "unknown"} (${rev?.[2] ?? "no digest"}) and these trails at these heads, `
					+ `as project.py status --for ${trail.name} prints them:\n${heads.join("\n") || "none"}`, 8000),
				links: [{ relation: "about", target: "step-0", status: "confirmed" }, ...heads.map((target) => ({ relation: "about", target, status: "confirmed" }))],
			});
			return { content: [{ type: "text", text }], details: {} };
		},
	});

	// The stock bash tool, one command at a time, so each observation is of its own run. Its exec is
	// wrapped to keep what the tool's result drops: the exit code, and whether the command wrote metrics.
	const local = createLocalBashOperations();
	pi.registerTool({
		...createBashToolDefinition(process.cwd()), executionMode: "sequential",
		async execute(id, params, signal, onUpdate, ctx) {
			const tool = createBashToolDefinition(ctx.cwd, { operations: { exec: async (command, cwd, options) => {
				const kept = pending.get(id);
				if (kept) Object.assign(kept, { before: stamp(join(kept.cwd, METRICS)), started: Date.now() });
				const wrap = box ? sandboxArgs(box) : [];
				let run = box ? sandboxedCommand(command, wrap) : command;
				if (kept && strace) {
					kept.trace = join(mkdtempSync(join(tmpdir(), "notebook-trace-")), "trace");
					run = tracedCommand(command, strace, kept.trace, wrap);
				}
				try {
					const result = await local.exec(run, cwd, options);
					if (kept) kept.exitCode = result.exitCode;
					return result;
				} finally {
					if (kept) settle(kept);
				}
			} } });
			return tool.execute(id, params, signal, onUpdate, ctx);
		},
	});

	// Fresh metrics only: the file counts when this command made it or changed it. An earlier
	// command's numbers, still on disk, are not this one's.
	function settle(kept: Pending): void {
		if (kept.ended !== undefined) return;
		kept.ended = Date.now();
		const path = join(kept.cwd, METRICS);
		const after = stamp(path);
		kept.fresh = after.exists && (!kept.before.exists || after.modified !== kept.before.modified) ? readFileSync(path) : null;
		if (kept.trace) {
			// A trace that was never written means the command did not start under strace: unknown, not empty.
			kept.reads = existsSync(kept.trace) ? readsOf(readFileSync(kept.trace, "utf8"), kept.cwd) : undefined;
			rmSync(dirname(kept.trace), { recursive: true, force: true });
		}
	}

	pi.on("tool_call", async (event, ctx) => {
		if (!trail.steps.length) return { block: true, reason: NOT_STARTED };
		const over = await ceiling();
		if (over) return { block: true, reason: over, terminate: true };
		if (isToolCallEventType("write", event) || isToolCallEventType("edit", event)) {
			const path = event.input.path.startsWith("~/") ? join(homedir(), event.input.path.slice(2)) : resolve(ctx.cwd, event.input.path);
			const target = real(path);
			if ([config.trail, config.store].some((root) => target === real(root) || target.startsWith(real(root) + sep)))
				return { block: true, reason: "The trail and its store are written only by capture." };
		}
		if (!isToolCallEventType("bash", event)) return;
		const plan = trail.latest("plan");
		if (!plan) return { block: true, reason: NO_PLAN };
		const command = event.input.command;
		if (!command.trim()) return { block: true, reason: "The command is empty, so there is nothing to run." };
		// From here an error is thrown, which blocks the command: one that cannot be recorded does not run.
		code = snapshot(ctx.cwd, trail.name, code);
		const lock = join(ctx.cwd, "uv.lock");
		const inputs = task.inputs.filter((path) => existsSync(join(ctx.cwd, path)))
			.map((path) => ({ ref: `file:${path}`, digest: digest(readFileSync(join(ctx.cwd, path))) }));
		const run = await trail.write(runStep(command, code, existsSync(lock) ? digest(readFileSync(lock)) : undefined,
			parameters(command, task.public_parameters), inputs, plan));
		pending.set(event.toolCallId, { run, plan, cwd: ctx.cwd, before: stamp(join(ctx.cwd, METRICS)), started: Date.now() });
	});

	pi.on("tool_result", async (event) => {
		const kept = pending.get(event.toolCallId);
		if (!kept) return;
		pending.delete(event.toolCallId);
		settle(kept);
		const measures = kept.fresh ? readMetrics(kept.fresh) : null;
		let metrics: Metrics | null = null;
		if (kept.fresh && measures) {
			metrics = { digest: digest(kept.fresh), measures };
			mkdirSync(config.store, { recursive: true });
			const stored = join(config.store, metrics.digest.split(":")[1]);
			// Agents running at once share the store: the file is created whole by one of them, never twice.
			try {
				writeFileSync(stored, kept.fresh, { flag: "wx" });
			} catch (error: any) {
				if (error?.code !== "EEXIST") throw error;
			}
		}
		const observation = await trail.write(observationStep(kept.run, kept.plan, kept.exitCode ?? -1, kept.ended! - kept.started, metrics, kept.reads));
		let line = receipt(kept.run, observation, kept.plan);
		if (kept.fresh && !measures) {
			await trail.write(noteStep(observation, "pi:tool_result", `${METRICS} was not usable for ${observation.id}`,
				`The command wrote ${METRICS}, but it is not one object of measure names to finite numbers, so ${observation.id} has no measures.`));
			line += `\n[notebook] ${METRICS} must be one JSON object of measure names to numbers; this one was not read.`;
		}
		return { content: [...event.content, { type: "text" as const, text: line }] };
	});
}
