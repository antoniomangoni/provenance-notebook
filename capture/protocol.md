# Working under the notebook

Your work is recorded as a trail that a reviewer reads later, without you. The record is made for you by the tools; these rules keep it true.

1. **Plan before any command.** Call `propose_plan` before `bash`. Say what you expect before you see the result: a measure the task declares, a comparison and a threshold.
2. **Looking around is a plan too.** To list files or read data, propose a plan whose only expectation is `exit_ok` on measure `exit`.
3. **Numbers come from a file.** A run reports its measures by writing `out/metrics.json`: one JSON object of measure names to numbers. A number that is only printed is not recorded.
4. **Read the receipt.** Each command's result ends with a line such as `[notebook] run step-5, observation step-6: contradicted (auc 0.58, expected >= 0.75)`. It gives the outcome and the step ids.
5. **Replace a contradicted plan.** Call `propose_plan` again with `supersedes` set to the old plan's id and `triggered_by` set to the observation's id from its receipt, and say in `reasoning` what the result changed. Do not repeat a run until it holds.
