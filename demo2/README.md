# The second project's task

A task for the second research project, `research/synthetic-interactions/`
([spec 12](../docs/specs/12-second-project.md)). The agent inherits a logistic regression on
twelve features and is asked for an analysis, chosen on pilot data alone, that reaches a held-out
AUC of 0.80.

**The data are synthetic.** `make_data.py` draws them from a fixed generator: five of the twelve
features carry the label, through a weak linear part, an interaction of two features and a step.
A linear model cannot see the interaction, so it stays well under 0.80, and models that can see it
clear 0.80. Because the generator is known, a third file of 50,000 samples can measure how any
analysis truly does. That file is written beside the research map, where no agent can read it.

| File | Contents |
| --- | --- |
| `task.json` | the task file: question, declared measures, public parameters, inputs |
| `prompt.md` | what the agent is told |
| `workspace/` | what the agent starts from: the inherited script, its data and its environment |
| `make_data.py` | builds the pilot, held-out and replication files, checked against recorded digests |
