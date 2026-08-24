# Ablation — what each rung of the §4.4 ladder contributes

> `python benchmarks/ablation.py <project>`
> Re-run after any change to the synthesis path.

## Why this shape, not the one #153 specifies

#153 asks for five arms: baseline, trace-carved, mutation-first, CrossHair,
Hypothesis, MCP handoff. **Four of those are unbuilt** — #149 and #150 are still
open, and there are no CrossHair or Hypothesis integrations. A harness that
"compares" unimplemented strategies measures nothing while printing a table
that looks like evidence.

This compares what actually shipped: each rung of the strategy ladder is turned
off in turn against the same project.

| arm | rungs enabled |
|---|---|
| A0 | none — literal stubs only, i.e. pre-spec10 behaviour |
| A1 | + conftest fixtures (#143) |
| A2 | + mined constructions (#144) |
| A3 | + guard-aware mocks (#145) |

Yield counts **verified** tests, not generated ones. A test Gate 5 rejects is
not a contribution.

## Result — tests/fixtures/async_orm_project

```
arm                           gaps   gen  verified   yield    sec
-----------------------------------------------------------------
A0 literal stubs only            4     4         0      0%    3.5
A1 + conftest fixtures           4     4         3     75%    2.8
A2 + mined constructions         4     4         3     75%    2.9
A3 + guard-aware mocks           4     4         3     75%    2.9
```

### What this establishes

**A0 = 0 verified reproduces the original failure exactly.** The 0-for-0 report
in spec10 §0 was not a misconfiguration; it is what the engine did on
async/ORM code before #143.

**RETRACTED — this claim was wrong.** It previously read *"#143 does all the
work here: 0 → 3. Reusing the project's own `db_session` is the single change
that moved this fixture."*

A leave-one-out lattice falsifies it. `constructions` **alone** also scores 3
on this fixture, and removing `fixtures` from the full ladder costs nothing:

```
Marginal contribution (full ladder minus each rung) — async_orm_project
  constructions   +0
  fixtures        +0
  guard_mocks     +0
```

All three are **perfect substitutes** here: any one alone reaches 3, so no rung
is necessary even though the ladder collectively takes 0 → 3. The cumulative
A0 ⊂ A1 ⊂ A2 ⊂ A3 design credited rung 1 purely because it is tried first. A
nested chain cannot distinguish "necessary" from "runs earliest", and reading
attribution off one is a mistake this document made and published.

On `no_fixture_project`, where the rungs are not substitutes, attribution is
real:

```
  constructions   +2
  fixtures        +0   <- removing it costs nothing here
  guard_mocks     +1
```

So across both benchmark fixtures **`fixtures` (#143) has zero measured
marginal contribution.** It may still matter on real projects — the async
fixture was built around a `db_session`, and rung 2 only substitutes for it
because that fixture also happens to contain literal construction sites — but
nothing here demonstrates it.

**#144 and #145 contribute nothing on this fixture — as predicted.** Both PRs
stated that this fixture's parameters are already fixture-covered, so rungs 2
and 3 would not fire. The ablation confirms it rather than leaving it as an
assertion.

### What it does NOT establish

That #144 and #145 are worthless. They target projects with *no* matching
fixture, which this fixture is not. Proving those rungs needs a project whose
parameters no conftest supplies — that fixture does not exist yet and is the
obvious next addition.

A run against quelltest itself (80 guards) would sample a much larger and more
varied population. It is slow, because each arm verifies every gap and
verification injects violations into live source.

## Result — quelltest itself (84 gaps)

```
arm                           gaps   gen  verified   yield    sec
-----------------------------------------------------------------
A0 literal stubs only           84    49        20     24%  165.1
A1 + conftest fixtures          84    49        20     24%  164.5
A2 + mined constructions        84    49        20     24%  168.6
A3 + guard-aware mocks          84    49        20     24%  164.7
```

**Every arm is identical. The ladder contributes nothing on this codebase.**

That is a real result and it should not be explained away. What it says:

- quelltest is a library and CLI. Its guards take paths, strings, ints and
  flags — types the literal stubs in `sig_inspector` already handle, which is
  why the A0 baseline already reaches 24%.
- It has no `db_session`-style fixtures whose names match function parameters,
  so rung 1 never fires. Nothing constructs domain objects with literal
  arguments, so rung 2 never fires. Few guards read an attribute off a complex
  parameter, so rung 3 never fires.

The ladder was built for the async/ORM web-service shape described in
spec10 §0. On that shape it takes yield 0% → 75%. On library-shaped code it is
inert — neither helping nor hurting (runtime is flat across arms, so the
discovery passes cost nothing measurable).

## Result — tests/fixtures/no_fixture_project (the control for rungs 2 and 3)

A project deliberately built so rung 1 *cannot* fire: no conftest fixture
matches any parameter name. Domain objects are constructed with literal
arguments elsewhere (rung 2's input), and guards read attributes off complex
parameters (rung 3's input).

```
arm                           gaps   gen  verified   yield
-----------------------------------------------------------
A0 literal stubs only            3     3         0      0%
A1 + conftest fixtures           3     3         0      0%
A2 + mined constructions         3     3         1     33%
A3 + guard-aware mocks           3     3         2     67%
```

**Rung 2 (#144) is confirmed working for the first time: 0 → 1.**

It took a bug fix to get there. The first run of this fixture returned 0 for
every arm, because rung 2 broke boundary injection:

```
if amount_cents <= 0:     ->  settle(account=Account(id=0, ...), amount_cents=1)
                                              ^^^^ mutated, and not the target
```

`_inject_boundary_value` used `re.sub(r"=\d+", ..., count=1)`, which
before #144 was harmless because every argument was a literal. Once an argument
could be a nested constructor, the first `=<digits>` was `id=1` *inside*
`Account(...)`. The constructor was corrupted, `amount_cents` was left at 1, the
guard never fired, and Gate 4 rejected the test. Fixed by targeting top-level
arguments only, preferring the guard's own variable.

**Rung 3 (#145) had never run at all.** The earlier explanation here -- that
rung 3 was unreachable whenever rung 2 succeeded -- was wrong. The real cause
was simpler: `_apply_guard_mock` was defined and **never called**. #145 shipped
as dead code, so the A3 column could not differ from A2 under any conditions.

Two further bugs sat behind it once it was wired in:

- Rungs 2 and 3 were written as alternatives. `_apply_guard_mock` only fired on
  a parameter still stubbed `=None`, which rung 2 had already replaced with a
  real constructor. They now compose: the guarded attribute is violated *on*
  the mined construction (`Account(owner_email=None)`), which is a better test
  subject than a mock because the rest of the object stays authentic.
- `_top_level_kwargs` took the first `(` in an expression. For a mined
  construction that is `__import__(`, not the constructor, so it parsed the
  wrong argument list and found no attribute to violate.

After all three fixes, A3 reaches 2 of 3 on this fixture.

## Reading these tables honestly

A flat yield across A1–A3 means "these rungs did not fire here", not "these
rungs do not work". Only A0 vs A1 on the async fixture is a difference these
runs can actually speak to.

**The measured evidence for the whole §4.4 ladder is currently: 0 → 3 verified
tests on one 4-guard fixture.** That is thin. It is consistent with the
production report in spec10 §0 that motivated the work, and the A0 = 0 result
reproduces that failure exactly — but one small fixture is not a benchmark.

What would strengthen it, in order:

1. ~~A second fixture with no matching conftest fixtures.~~ Done -- it is
   `no_fixture_project`, and it confirmed rung 2 while exposing the boundary
   bug and the rung-2/rung-3 conflict above.
2. ~~Make rung 2 and rung 3 compose.~~ Done. Every rung now has at least one
   project where it demonstrably contributes: rung 1 on the async fixture
   (0 -> 3), rung 2 here (0 -> 1), rung 3 here (1 -> 2).
3. A real third-party async backend, which is the population spec10 §0 came
   from. Still the only thing that would settle whether any of this holds at
   scale -- two small fixtures are not a benchmark.
