# Spec: the review memory

A spec a machine can check (Session 14). A fresh agent, or a future me, can change `memory.py` from
this file alone, and the command at the bottom decides whether the change is done.

## Goal

Researchers and reviewers should not check the same doubtful paper twice, and a past decision must
never outlive the text it was about.

## Must hold

1. One live verdict per paper. A new verdict supersedes the old one, and the old one stays in history.
2. An approval covers the exact passage it judged. If that text changes, the flag comes back.
3. A paper marked wrong or poisoned warns on every answer that read it, without a new review item.
4. The same question with the same reasons is one open review item, counted, not queued twice.
5. An explanation of a flag comes from the log, and names every check and paper in it and no others.
6. One person's question is never shown to another person.
7. The memory never enters a model prompt.
8. If the memory cannot be read or written, the answer is still returned and no flag is dropped.
9. A withheld answer's text is never stored, and a code inside a reviewer's note is withheld too.

## Out of scope

Per-user memory, automatic verdicts, semantic search over notes, and a reviewer interface.

## Done when

This command exits 0:

```bash
uv run --project 01_Product_Engineering/challenge --with pytest python -m pytest tests/test_ladder.py tests/test_memory_scenarios.py -q
```

`tests/test_memory_scenarios.py` runs each scenario against the real memory and against a memory broken
on purpose. A scenario that cannot tell them apart fails the command.

## Budget

Stop after three attempts at the same failing test and ask a person. A loop that cannot fail is a hang.
