# callback-hotpath-io

Flag HF `Trainer` callback methods whose body contains per-event
filesystem IO (`Path.open`, bare `open`, `Path.mkdir`, `write_text`,
`write_bytes`).

Signal:
  - Method is a member of a class that inherits from any `*Callback`
    / `TrainerCallback` base (matched by bare-name ancestry, since we
    don't resolve imports).
  - Method name matches `on_(step|log|evaluate|train_*|batch_*|epoch_*|predict_*|save|init_*)`.
  - Method body calls `open`, `Path.open`, `.mkdir`, `.write_text`,
    `.write_bytes`.
  - The call is not inside an attribute-cache guard
    (`if self.opened is None: ...`) - we can't verify that
    mechanically, so the check is coarse: any such call is flagged.

One-time setup belongs in `__init__`; if the setup cannot move there
(rare), add `# auditme: accept <reason>`.
