# Synthesis: *Code Red* → a maintainability MCP server for agentic C++

This note distils the paper and its most relevant references into design decisions
for an MCP server that scores, explains, and improves the maintainability of
agent-generated C++.

Bracketed numbers refer to the reference index in [`manifest.json`](manifest.json)
and [`references.bib`](references.bib); `[000]` is the paper itself.

---

## 1. The paper in one page

**Tornhill & Borg, *Code Red: The Business Impact of Code Quality* (TechDebt 2022) [000].**

The study links CodeScene's **Code Health** score to three outcomes across
39 proprietary codebases (30,737 files, 6–12 months of history, 14 languages,
**primarily C++**):

| Outcome | Healthy (≥ 8.0) | Warning (4.0–8.0) | Alert (< 4.0) | Effect |
|---|---:|---:|---:|---|
| Avg. Jira defects / file | 0.25 | 0.94 | 3.70 | **~15×** more in Alert |
| Avg. Time-in-Development / file | 7,816 min | 13,935 min | 17,545 min | **+124%** Alert vs Healthy |
| Max Time-in-Development / file | 15,112 min | 34,025 min | 129,940 min | **~9×** Alert vs Healthy |

- Warning code is already **78% slower** than Healthy code.
- Code Health correlates with issue-resolution time at **r = −0.58**; raw LoC
  correlates at only **r = 0.13**.
- Effects are statistically significant (Kruskal–Wallis, ANOVA, DSCF/Tukey;
  Cohen's *d* = 0.73 for defects, 0.45 for average time, 0.96 for maximum time).
- Code Health is a **1.0–10.0** score built from ISO 5055 maintainability
  characteristics plus design-level smells (God Class, God Method, duplicated
  code) [000, §2.1].
- Code Health has also been reported to predict security vulnerabilities [001].

**The one-sentence takeaway:** a composite, smell-aware maintainability score is
a far better proxy for defect risk and change cost than lines of code, and the
effect is large enough to justify gating and feedback.

---

## 2. What the paper actually establishes — and what it does not

### Established

- A strong **association** between low Code Health and more defects, longer
  development time, and less predictable completion.
- The association holds across many organisations and domains, with C++ as the
  dominant language.
- A **graded** relationship: the Warning band already carries a substantial
  penalty, not just the Alert band.

### Not established

- **Causality.** The authors explicitly accept that low quality may both cause
  defects and be caused by them (or by time pressure, process, or organisation)
  [000, §5.4; 019, 033, 041].
- **Generalisability to agentic code.** The corpus is human-written production
  code from CodeScene customers. Agent-generated code may have a different smell
  distribution (more duplication, weaker architectural cohesion, more
  boilerplate).
- **Exact metric reproducibility.** Code Health is proprietary and calibrated
  against a hand-scored baseline library. Our score can only be an
  *approximation*.
- **Language causation.** A reproduction study found only weak, small-effect
  language/defect associations and no causal story [006].

**Design consequence:** use the paper as *motivation and calibration prior*, not
as proof. Report confidence, keep the score explainable, and validate the
predictive power of our own metric against agentic outcomes (rework, test
failures, time-to-green).

---

## 3. Why this matters for agentically generated C++

Agents optimise for local correctness and short-term task completion. That
failure mode maps directly onto the smells Code Health penalises:

- **God functions / god classes** produced by "just add another branch" edits.
- **Duplication** because the agent copies a nearby pattern instead of
  extracting an abstraction.
- **Deep nesting and long parameter lists** from incremental patching.
- **Poor cohesion and high coupling** when new behaviour is bolted onto an
  existing type.
- **C++-specific debt**: raw `new`/`delete`, Rule-of-0/3/5 violations, missing
  `const`/`noexcept`/`override`, heavy header includes, template and macro
  complexity, exception-unsafe code, and ODR/UB-prone patterns.

The paper's comprehension evidence reinforces the point: developers spend roughly
60% of their time understanding code [063], understanding is the dominant
maintenance activity [025], and anti-patterns measurably increase comprehension
time and effort [049]. Code smells and refactoring are strongly tied to
understandability, maintainability, testability, complexity, functionality, and
reusability [034]. If an agent leaves code harder to understand, it is
externalising cost onto every future change.

The broader technical-debt literature agrees on the size of the problem:
developers lose ~23% of time to debt in a longitudinal study [010], ~36% in an
interview study [008], and up to 42% in an industry report [057]. Yet only a
small minority of organisations track debt methodically [038]. Automated,
continuous measurement is therefore the missing feedback signal — exactly what
an MCP server can supply inside the agent loop.

---

## 4. Related work: agentic maintainability and MCP

The original corpus predates the current wave of agentic coding. This section
adds the most relevant recent work and positions the server against it.

### 4.1 LLM-generated code and maintainability

- **LLMs can assess maintainability.** Dillmann et al. [065] show that the
  cross-entropy of code under an LLM is associated with expert ratings of
  readability, understandability, complexity, modularisation, and overall
  maintainability, after controlling for logical LoC. This is a promising
  *pre-screening* signal, not a replacement for deterministic analysis.
- **The evidence on LLM vs. human code is mixed.** Santa Molison et al. [073]
  compare maintainability and reliability of LLM-generated and human-written
  code; results are context-dependent. Rönnqvist et al. [074] study
  maintainability-related metrics specifically for LLM-generated **C++**, the
  closest prior work to this project.
- **Smell propensity is measurable.** Velasco et al. [070] introduce
  CodeSmellEval and the Propensity Smelly Score; CodeLlama and Mistral both
  produce smells such as simplifiable conditions and mergeable `isinstance`
  checks. Souza et al. [071] find that LLMs detect structurally straightforward
  smells well, but are weaker on context-dependent ones.
- **Predict before generating.** PreMaQ [072] predicts Code Smell Score and
  Maintainability Index from an LLM's internal representations *before*
  generation, suggesting an optional "pre-flight" risk estimate.
- **Cognitive complexity is a validated proxy.** Lavazza et al. [078] evaluate
  cognitive complexity as a predictor of code understandability, supporting its
  use in the scoring model.

**Implication:** use LLMs as a triage/explanation layer and as an optional
pre-generation risk estimator; keep deterministic analyzers as the source of
truth for the score.

### 4.2 Technical debt in AI-assisted development

- **Debt persists in the wild.** Liu et al. [068] analyse 302.6k AI-authored
  commits from 6,299 repositories and run static analysis before and after;
  quality issues are not always fixed quickly and can accumulate as debt.
- **Practitioners worry about more than code.** Jahan et al. [067] survey 137
  practitioners and interview 20; the strongest concerns are People Debt
  (73.0%), Management Debt (70.1%), and Architecture Debt (68.6%), driven by
  ambiguous requirements, insufficient project context, and unrequested AI
  changes.
- **The Triple Debt Model.** Storey [069] distinguishes technical debt in code,
  **cognitive debt** (erosion of shared understanding), and **intent debt**
  (missing externalised rationale). An agent can produce code that is locally
  clean but increases cognitive and intent debt.
- **The survey evidence is mixed.** Matias et al. [066] report productivity and
  comprehension gains alongside hallucinations, unstable outputs, and new forms
  of debt.

**Implication:** maintainability is not only code metrics. Add cognitive/intent
debt signals (missing rationale, unexplained magic, absent ADRs) and report them
separately from the code score.

### 4.3 Feedback, critics, and self-refinement

- **LLM code review works, with caveats.** Rasheed et al. [075] use an LLM agent
  to detect smells, bugs, and improvement opportunities; it complements, rather
  than replaces, static analysis.
- **Critics catch real bugs.** McAleese et al. [076] train critic models that
  are preferred over human critiques in 63% of cases and catch more bugs than
  paid human reviewers on naturally occurring LLM errors.
- **Execution feedback closes the loop.** Ding et al. [077] show that
  self-refinement with test/execution feedback improves code generation
  (CYCLE). The same principle applies to maintainability feedback.

**Implication:** use an optional LLM critic to triage false positives and write
explanations, and incorporate test/execution signals into the loop. The
deterministic score remains authoritative.

### 4.4 Agentic software engineering and benchmarks

- **SE 3.0.** Hassan et al. [079] argue for a duality of SE for Humans and SE
  for Agents, with Agent Command and Agent Execution Environments. Tooling must
  be designed for agents as first-class users.
- **Benchmarks are misaligned.** Gorinova et al. [080] show that end-to-end
  pass/fail conflates model, harness, environment, and feedback signals; they
  call for component-level signals and iteration-aware evaluation.
- **Live and verified benchmarks.** SWE-bench-Live [081] and SWE-Bench Pro
  Verified [082] address contamination and reproducibility.

**Implication:** evaluate the server on component-level metrics (score delta,
iterations, rework, time-to-green) and on live/verified benchmarks, not only on
task success.

### 4.5 MCP ecosystem and security

- **MCP servers are software too.** Hasan et al. [083] study the security and
  maintainability of MCP servers; the ecosystem has recurring quality and
  security issues.
- **Adoption and evaluation.** Chen et al. [084] study enterprise adoption;
  Majeed et al. [085] empirically study MCP applications; Li et al. [086]
  document security issues; Luo et al. [087] evaluate MCP servers.

**Implication:** apply MCP security best practices: least privilege, strict
input validation, no arbitrary command execution, subprocess sandboxing, audit
logging, and a small, maintainable codebase.

### 4.6 Competitive landscape

- **SonarQube MCP Server + Sonar Vortex** is the closest commercial analogue:
  a **Guide** phase (inject standards/context before generation) and a
  **Verify** phase (scan the agent's edits inside the loop), local stdio,
  toolsets, CI-context reuse, and C++ support. It is Docker-based; we
  deliberately diverge (no Docker) and focus on open-source, transparent,
  calibratable Code Health–like scoring.
- **`CHOCEK-RB/cpp-mcp`** exposes clangd, CMake, C++ Core Guidelines, and SEI
  CERT to agents.
- **`hy-min/cpp-sentinel`** combines clang-tidy with LLM triage.
- **`noonafter/mcp_cppcheck`** wraps cppcheck.
- **`witold-andelie/revio`** orchestrates 13 deterministic analyzers plus LLM
  reasoning and a grounding validator.

**Implication:** reuse or contribute to these where possible; differentiate on
the maintainability score, the feedback loop, and C++-specific prioritisation
rather than on re-implementing analyzers.

---

## 5. A maintainability model for the MCP server

### 5.1 Dimensions and measurable proxies

The goal is a Code Health–like score built from **observable, local, C++
specific** signals. Each dimension maps to one or more analyzers.

| Dimension | Proxy metrics | Primary tool(s) |
|---|---|---|
| Size | logical LoC per file/function/class; number of methods/fields | lizard, libclang |
| Cyclomatic complexity | McCabe per function; decision points | lizard, clang-tidy |
| Cognitive complexity | nesting + breaks in linear flow | custom libclang, Sonar-like rules |
| Nesting | max depth of control structures | libclang |
| Interface width | parameter count, boolean flags, out-params | libclang, clang-tidy |
| Cohesion | LCOM / lack of cohesion per class | libclang |
| Coupling | fan-in/fan-out, CBO, include graph | libclang, include-what-you-use |
| Duplication | token-based clone ratio | PMD CPD, jscpd |
| God class / god method | size × complexity × coupling | composite of the above |
| Readability | comment density, naming, magic numbers | clang-tidy readability-* |
| Resource safety | raw `new`/`delete`, `malloc`/`free`, Rule of 0/3/5 | clang-tidy cppcoreguidelines-*, custom AST |
| Exception safety | `catch (...)`, throwing destructors, missing `noexcept` | clang-tidy, custom AST |
| Header hygiene | include guards, `#pragma once`, heavy includes, cycles | include-what-you-use, custom |
| Template/macro complexity | template depth, SFINAE, macro density | libclang, custom |
| Static-analysis debt | warning density by severity | clang-tidy, clang static analyzer, cppcheck |
| Testability | seams, global state, hidden dependencies | custom heuristics + coverage if available |
| Build weight | header fan-out, preprocessed size | clang `-E`, include graph |
| Cognitive/intent debt | missing rationale, unexplained magic, absent ADRs, low comment quality | custom heuristics + optional LLM critic |

Cognitive and intent debt [069] are reported **separately** from the code score:
they capture whether the agent (or human) left enough rationale for the next
reader. A file can score well on code metrics and still be expensive to change
because nobody knows *why* it works.

### 5.2 Scoring

Use a **weighted, saturating penalty model**, not a linear sum:

```
score(file) = 10 − Σ_d  w_d · penalty_d(file)
penalty_d   = min(1, max(0, (value_d − good_d) / (bad_d − good_d)))
```

- `good_d` / `bad_d` are per-dimension thresholds calibrated to the Code Health
  bands (Healthy ≥ 8.0, Warning 4.0–8.0, Alert < 4.0).
- Weights should reflect the paper's effect sizes: defect risk and maximum
  cycle time are the strongest signals, so complexity, duplication, and
  god-class/god-method penalties should dominate.
- Normalise by file type and size so generated tables, enums, and data files are
  not punished for being large.
- Produce **file-level and function-level** scores; the function level is what
  the agent can act on.
- Always return the **contributing findings**, not just the number.

### 5.3 Calibration

1. Start from the paper's bands and the smell taxonomy in [034].
2. Build a corpus of known-good and known-bad C++ (e.g., Abseil, LLVM, Qt,
   GoogleTest, plus deliberately degraded variants).
3. Have humans rate a stratified sample; correlate the score with expert
   judgement.
4. Validate predictive power on agentic tasks: does a lower score predict more
   rework, more test failures, or longer time-to-green?
5. Recalibrate weights with the observed effect sizes; keep the calibration
   dataset and script in the repo.

### 5.4 What not to do

- **Do not use raw LoC as the primary metric** — the paper's r = 0.13 [000] and
  the critique in [002] both argue against it.
- **Do not rely on SonarQube rule counts alone** — a study found no clear link
  between individual violations and lead time [036], while CodeScene's
  higher-level metric was more significant in a student project [014].
- **Do not emit an opaque score** — every point lost must be traceable to a
  finding with a file, range, rule, and suggested fix.
- **Do not treat the score as ground truth** — it is a proxy, and the paper is
  observational.

### 5.5 Optional pre-generation risk (PreMaQ-style)

If a compatible model is available, estimate the risk of a task *before*
generation from the prompt and repository context [072]. Treat this as a
prioritisation hint, not a gate: the post-edit scan remains authoritative.

---

## 6. MCP server architecture

### 6.1 Tools

The server has two modes, mirroring the Guide/Verify split used by agentic
tooling (§4.6):

- **Guide** — before generation, inject project conventions, C++ Core
  Guidelines, and prior findings so the agent writes maintainable code in the
  first place.
- **Verify** — after edits, scan the diff and return ranked findings.

| Tool | Mode | Purpose | Key inputs | Output |
|---|---|---|---|---|
| `guide` | Guide | Pre-generation context | `paths`, `task`, `standards` | relevant guidelines, conventions, prior findings |
| `maintainability_scan` | Verify | Full or incremental scan | `paths`, optional `diff`, `config` | score + findings |
| `maintainability_score` | Verify | Fast score only | `paths` | 1–10 score, band, per-dimension breakdown |
| `explain_finding` | Verify | Why a finding matters | `finding_id` | rationale, evidence, minimal fix |
| `suggest_refactorings` | Verify | Ranked, minimal-diff actions | `paths`, `budget` | ordered refactoring plan |
| `compare_revisions` | Verify | Regression gate | `before`, `after` | delta, new/resolved findings, pass/fail |
| `track_trend` | Verify | History over time | `repo`, `window` | score/defect/rework trend |
| `baseline` | Verify | Snapshot for gating | `repo` | stored baseline |

Expose tools in **toolsets** so clients can keep context small: `core` (scan,
score, explain, suggest, compare), `guide`, `security`, `dependencies`, and
`trends`. The default should be `core` + `guide`; everything else is opt-in.

### 6.2 Analyzer stack (Python)

- **clang-tidy** — `bugprone-*`, `readability-*`, `performance-*`,
  `cppcoreguidelines-*` by default; a project `.clang-tidy` takes precedence.
- **Clang static analyzer** — path-sensitive bug finding.
- **cppcheck** — SARIF output; cheap, broad coverage; good for CI.
- **lizard** — function/file complexity, LoC, parameter counts.
- **PMD CPD / jscpd** — token-based duplication.
- **libclang (`clang.cindex`)** — in-process AST metrics: class size, method
  length, nesting, cohesion, coupling, include graph, template depth.
- **include-what-you-use** — header hygiene (optional, expensive).
- **compile_commands.json** — used as a source of include paths, defines, and
  the C++ standard; the server auto-discovers it and falls back to the config's
  `include_paths`/`defines` when it is absent.

**Version-aware discovery.** The server resolves `clang-tidy-{version}`,
`clang-{version}`, `scan-build-{version}`, and `llvm-config-{version}` from a
configurable `clang_version` (auto-detected highest if unset), then falls back
to the unversioned names. `cppcheck` is resolved as `cppcheck-{version}` then
`cppcheck`. libclang is loaded in-process from
`/usr/lib/llvm-{version}/lib/libclang.so` (or the configured path) via
`clang.cindex.Config.set_library_file`. Analyzer subprocesses run with a
sanitized environment (`clean_env`, default `LD_LIBRARY_PATH` removed) so a
project's module environment does not break the versioned tools; the agent's
build commands are unaffected.

**Header coverage.** The server analyzes files directly. `compile_commands.json`
is used only as a source of include paths, defines, and the C++ standard:
`.cpp` files use their own compile command, headers use the union of include
paths/defines, and without a database the config's `include_paths`/`defines`
are used. Header analysis uses `-x c++-header` for clang-tidy/libclang and
`--language=c++` for cppcheck. Project-wide scans use a fast path (fast
analyzers plus `cppcheck --project -j`); single-file and diff scans run the
external analyzers directly. There is no translation-unit sweep.

Normalise every tool's output into one **Finding** schema (SARIF is a good
interchange format; cppcheck emits SARIF on stderr, clang-tidy emits text
diagnostics).

### 6.3 Finding schema

```json
{
  "id": "sha1:...",
  "file": "src/foo.cpp",
  "range": {"start": {"line": 42, "column": 3}, "end": {"line": 88, "column": 1}},
  "rule": "god-function",
  "dimension": "complexity",
  "severity": "warning",
  "message": "Function 'process' has cyclomatic complexity 34 and 7 parameters.",
  "evidence": {"cyclomatic": 34, "parameters": 7, "loc": 180},
  "suggested_fix": "Extract the validation and serialisation branches into helpers.",
  "impact": {"defects": 0.8, "time": 0.7, "predictability": 0.6},
  "effort": "M",
  "confidence": 0.9
}
```

### 6.4 Feedback loop

```
guide(task, paths)  ──►  standards + conventions + prior findings
        │
        ▼
agent writes/edits C++
        │
        ▼
maintainability_scan(diff)  ──►  findings + score
        │
        ▼
rank by impact / effort  ──►  top-k actionable findings
        │
        ▼
agent applies minimal fixes
        │
        ▼
compare_revisions(before, after)  ──►  delta + gate
        │
        └── repeat until score ≥ threshold or budget exhausted
```

Guidelines:

- **Guide before verify.** Inject standards and prior findings before
  generation; verification is cheaper than repair.
- **Small batches.** Feed the agent the top 3–5 findings, not the whole list;
  large feedback sets cause thrashing and context overflow.
- **Actionable fixes.** Each finding should name a concrete refactoring
  (extract function, split class, replace raw loop with algorithm, introduce
  RAII, reduce include fan-out).
- **Gate on regressions.** Fail if the score drops below the baseline or if a
  new Alert-band function appears.
- **Track process metrics.** Iterations to threshold, score delta per iteration,
  rework rate, time-to-green. These are the agentic analogues of
  Time-in-Development and the DORA metrics [054].
- **Detect gaming.** Flag `// NOLINT`, `#pragma GCC diagnostic ignored`,
  `catch (...)`, dead-code suppression, and score-only edits. Penalise
  suppressions unless justified.

### 6.5 Caching and performance

- Content-address the cache by file hash + analyzer version + config.
- Analyse only changed translation units on incremental runs.
- Run analyzers in subprocesses with timeouts and memory limits.
- Store history in SQLite (score, findings, commit, timestamp) for trends and
  regression gates.
- Prefer a fast path (`lizard` + `cppcheck` + duplication) for the inner loop and
  a slow path (clang-tidy + static analyzer + libclang) for the gate.

### 6.6 Deployment without Docker

- The server is a local **stdio** process started by the agent:
  `uv run cpp-maintainability-mcp` (or `python3 -m cpp_maintainability_mcp`).
- Dependencies are pinned in `pyproject.toml` and installed into a project-local
  venv; no container runtime is required.
- Analyzers are invoked as subprocesses with timeouts and resource limits.
- Analyzer subprocesses receive a sanitized environment (`clean_env`): only
  `clean_env_vars` (default `LD_LIBRARY_PATH`) are removed, so the project's
  modules remain available to the agent's build commands.
- libclang is loaded in-process from the versioned shared library; no
  container or separate process is required.
- For untrusted code, add OS-level sandboxing (bubblewrap/firejail) or run the
  server under a dedicated low-privilege account. This is a deliberate
  trade-off: less isolation than a container, but simpler and faster for local
  agent use.
- Apply MCP security practices [083, 086]: least privilege, strict input
  validation, no arbitrary command execution, and audit logging.

---

## 7. C++-specific rule catalogue

Start with a small, high-signal set; expand only when validated.

**Structure and size**
- Function length, cyclomatic complexity, cognitive complexity, nesting depth.
- Parameter count and boolean-flag parameters.
- Class size, method count, field count, LCOM.
- God class / god method composites.

**Duplication and abstraction**
- Token-clone ratio per file and per project.
- Repeated switch/if-else chains that should become polymorphism or a table.
- Copy-pasted error handling.

**Resource and lifetime safety**
- Raw `new`/`delete`, `malloc`/`free`, owning raw pointers.
- Rule of 0/3/5 violations; missing virtual destructors.
- `catch (...)`; throwing destructors; missing `noexcept` on move operations.
- Use of `std::unique_ptr`/`std::shared_ptr` where ownership is unclear.

**Modern C++ hygiene**
- Missing `const`, `override`, `final`, `[[nodiscard]]`.
- Narrowing conversions, signed/unsigned mismatches.
- Prefer `std::string_view`, `std::span`, `std::optional`, `std::variant`,
  `std::algorithm` over hand-rolled loops.
- `using namespace` in headers.

**Headers and build**
- Missing include guards / `#pragma once`.
- Heavy includes in headers; missing forward declarations.
- Include cycles; unnecessary transitive includes.
- PIMPL opportunities for stable interfaces.

**Templates and macros**
- Excessive template depth, SFINAE-heavy interfaces.
- Macro-defined control flow or types.
- Preprocessor conditionals that fragment the code.

**Testability**
- Global/static mutable state.
- Hidden dependencies (singletons, service locators).
- Hard-coded I/O, time, randomness.

---

## 8. Mapping paper findings to design decisions

| Paper finding [ref] | Design decision |
|---|---|
| Alert code has ~15× more defects [000] | Weight defect-prone smells heavily; gate Alert-band code |
| Alert code takes +124% to resolve [000] | Use time-to-threshold and iteration count as loop metrics |
| Max cycle time is ~9× longer in Alert [000] | Track variance/predictability, not just the mean; flag high-variance files |
| Warning code is already 78% slower [000] | Warn early; do not wait for Alert |
| Code Health r = −0.58 vs LoC r = 0.13 [000] | Composite score, not LoC |
| Code Health includes design smells [000] | Integrate lizard, PMD CPD, libclang smell detectors |
| Code Health predicts vulnerabilities [001] | Include security-adjacent clang-tidy/cert rules |
| C++ is the dominant language [000] | Prioritise C++-specific rules and analyzers |
| Smells/refactoring affect understandability, testability, complexity [034] | Explain findings in comprehension terms, not just rule IDs |
| Anti-patterns increase comprehension time and effort [049] | Treat duplication and god classes as first-class penalties |
| ~60% of time is program comprehension [063] | Optimise feedback for *understanding*, not just line count |
| Developers lose 23–42% of time to debt [010, 057] | Frame the score as a productivity signal, not a style score |
| Few organisations track debt methodically [038] | Automate measurement and history by default |
| SonarQube rule counts did not predict lead time [036] | Avoid rule-count-only scoring; use higher-level composites |
| Language/defect associations are weak [006] | Do not over-index on language; focus on code-level structure |
| DORA metrics can be measured automatically [054] | Reuse the same idea for agentic process metrics |
| LLM cross-entropy predicts maintainability [065] | Optional pre-screening / pre-flight risk estimate |
| AI-generated code accumulates debt in the wild [068] | Track debt over time; gate regressions |
| Cognitive/intent debt [069] | Add rationale/understanding signals, not just code metrics |
| LLM critics catch bugs [076] | Optional critic for triage/explanation; deterministic score authoritative |
| Benchmarks need component-level signals [080] | Evaluate score delta, iterations, rework, time-to-green |
| MCP servers have security/maintainability issues [083] | Apply MCP security practices; keep server small |
| Sonar Vortex uses Guide/Verify (competitive) | Adopt Guide + Verify; no Docker |

---

## 9. Evaluation plan

1. **Unit-level validity.** Compare the score against expert ratings on a
   stratified C++ sample; report correlation and disagreement cases.
2. **Predictive validity.** On agentic tasks, test whether lower scores predict
   more rework, more test failures, and longer time-to-green.
3. **Feedback efficacy.** A/B test: no feedback vs score-only vs score + top-k
   actionable findings. Measure final score, iterations, and human review time.
4. **Gaming resistance.** Inject prompts that encourage suppression or
   score-only edits; verify the server detects and penalises them.
5. **Performance.** Measure scan latency on small, medium, and large
   translation units; ensure the inner-loop fast path is usable interactively.
6. **Reproducibility.** Pin analyzer versions, ship the calibration corpus, and
   record configuration in the manifest.
7. **Benchmark validity.** Run on SWE-bench-Live [081] and SWE-Bench Pro
   Verified [082]; report component-level signals (score delta, iterations,
   rework, time-to-green) rather than only task success [080].
8. **MCP security review.** Audit the server against MCP security guidance
   [083, 086]: input validation, least privilege, no arbitrary command
   execution, and audit logs.

---

## 10. Risks and open questions

- **Proprietary metric gap.** Our score will not equal Code Health; validate
  against outcomes rather than claiming equivalence.
- **Observational evidence.** The paper is not causal; avoid causal language in
  tool output.
- **Agentic distribution shift.** Smell frequencies may differ from human code;
  recalibrate on agent-generated corpora.
- **False positives.** Static-analysis noise can mislead the agent; include
  confidence and allow justified suppressions.
- **Build integration.** Accurate C++ analysis needs `compile_commands.json`;
  CMake/Meson/Bazel integration is non-trivial.
- **Metric gaming.** Agents may optimise the score rather than the code; use
  multiple signals and human review.
- **Security.** Running analyzers on untrusted code requires sandboxing and
  resource limits.
- **MCP attack surface.** The server executes analyzers and reads source;
  validate inputs, avoid shell injection, and run with least privilege
  [083, 086].
- **LLM critic reliability.** Critics can be confidently wrong; use them for
  triage and explanation, not as the sole gate [076].
- **Cognitive/intent debt is hard to measure.** Rationale and shared
  understanding are not directly observable; treat these signals as heuristics.
- **No-Docker isolation trade-off.** Without containers, isolation depends on
  subprocess limits and optional OS sandboxing; document the residual risk.
- **Open questions.** What weights best predict agentic rework? How much
  feedback is optimal before the agent thrashes? Does the loop improve
  long-term maintainability or only the current score? How should the score
  handle generated code and third-party headers?

---

## 11. Next step

Phase 3: implement the Python MCP server skeleton with the Finding schema, the
Guide/Verify tools, toolsets, the fast/slow analyzer paths, the scoring engine,
and the `compare_revisions` gate. Run it as a local stdio process
(`uv run cpp-maintainability-mcp`, **no Docker**), then calibrate on a C++ corpus
and wire it into `opencode.json`.

Full citations and download status for every reference are in
[`manifest.json`](manifest.json); BibTeX is in [`references.bib`](references.bib).
