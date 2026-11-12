# Week 6 baseline review

Baseline commit: 45c5e162d494a025b0414f8f07e69fd9b39531d6

This is a source inspection, not an executed security assessment. No live model results are available yet.

## Confirmed implementation

- FastAPI web frontend delegates actions to the existing repository and LangGraph guidance service.
- Repository case reads and mutations enforce assignment checks. Formal workflow actions have additional gates.
- The web API accepts actor_id from the caller and resolves a synthetic demo principal. This supports demonstration persona switching; it is not authenticated identity binding.
- Live guidance already instructs the model that retrieved text is data rather than instructions. Citation validation checks references, not semantic truth or sensitive-output disclosure.
- Local mode returns evidence extracts without calling a generative model. Local-only tests cannot establish live-model jailbreak resistance.
- Uploads create unpublished candidate indexes. An uploaded injection fixture is not automatically part of active retrieval. Tests must prove reachability in an isolated corpus.
- Guidance responses include evidence and the original question as well as generated guidance. Sensitive-output protection must cover the returned payload, not just the summary.

## Three required defense workstreams

1. Strengthen and test retrieved-content isolation with controlled injected evidence and clean controls. Preserve the existing baseline instruction as an existing control, not a new addition.
2. Bind protected requests to a server-established test identity and enforce case scope. Preserve the existing repository authorization gates. Do not use a caller-controlled persona field as authentication.
3. Add sensitive-output screening before delivery, including evidence fields. Define synthetic protected fixtures and allowed disclosures, measure false positives, and distinguish seeded component tests from model-observed disclosures.

## Execution sequence

Install the locked dependencies and run existing tests in isolated temporary storage. Prepare 24 adversarial and six legitimate cases. Capture baseline results before modifying application defenses. Execute generation tests only in configured live mode, using locally supplied credentials without displaying them. Implement the three defenses and repeat relevant cases. Capture real demonstrations for the nine-minute walkthrough after findings are verified.

No deployment or remote repository changes have been made.

## Local verification completed

Installed the committed requirements.lock in an isolated Python 3.12 environment. The existing test suite passed: 14 tests in 34.61 seconds. These are existing functional tests, not the planned 30-case Week 6 assessment. No OpenAI credential is configured in this checkout, so live-model adversarial tests remain blocked. Application source and the deployed service remain unchanged.

## Live configuration follow-up

The user configured the local environment. A subsequent live smoke test succeeded with remote tracing disabled: hybrid retrieval returned six evidence items, GPT-5.4 Mini generated an answer to the coding-tool question, and citation-reference validation passed. Guidance elapsed time was 6.8368 seconds after index initialization. This supersedes the earlier credential blocker. It is a connectivity and functional smoke test, not semantic faithfulness validation or completion of the 30-case assessment.
