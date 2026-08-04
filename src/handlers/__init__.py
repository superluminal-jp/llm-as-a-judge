"""Step Functions step handlers for the LLM-as-a-Judge workflow.

The evaluation pipeline runs as three Lambda functions orchestrated by an
Express state machine, replacing the in-Lambda thread pool used by
:func:`src.handler.lambda_handler`:

    Prepare  ->  Map(EvaluateCriterion)  ->  Summarize

Moving the fan-out into the state machine buys three things the thread pool
could not provide:

* **Per-criterion retry.** Backoff and jitter are declared in the state machine
  and executed by the service, so a throttled criterion does not sit in
  ``time.sleep`` on billed Lambda time.
* **Bounded concurrency as configuration.** ``MaxConcurrency`` caps concurrent
  Bedrock calls in the state machine definition rather than depending on every
  caller passing the right ``max_parallel``.
* **Per-criterion visibility.** Each criterion is a state in the execution
  history, so a failure names itself instead of collapsing into one Lambda error.

All three handlers reuse the prompt construction, parsing, and aggregation
functions in :mod:`src.evaluator`; none of that logic is reimplemented here.

Payloads travel by claim check (see :mod:`src.jobs`) because Step Functions caps
inter-state data at 256 KB.
"""
