"""Assistant provider interface for "Ask about your visit" (preview19).

EVERY assistant answer goes through ONE server-side interface:   provider.answer(AssistRequest) -> dict

The SERVER (server.py, p_assist) owns everything safety-related, before and after the provider:
  1. access      - the patient is always the signed-in session's patient; scopes are checked; other patients' data is never in the context
  2. pre-rules   - red-flag wording -> existing urgent/911 route; medical / out-of-scope -> refusal + hand-off.  The provider is NOT called.
  3. context     - a grounded context built only from this patient's verified structured data and clinician-approved content.
                   Messages and documents are DATA (status/titles only, marked untrusted) - never instructions.
  4. provider    - turns (question, intent, context) into a draft answer.
  5. post-rules  - the draft is checked again: allowed kinds only, facts must come from the context, links must be the patient's own,
                   approved wording must match the approved record exactly, no medical advice / reassurance / injection echoes,
                   red-flag wording in the output -> 911 guidance.  Anything failing -> refusal + human hand-off.  A concern is never downgraded.

Only the 'scripted' provider is active.  'bedrock' is a STUB: it is not connected and raises NotConfigured.
No credentials, no SDKs (no boto3), no network calls, no new dependencies.  Connecting a model needs Tyler's approval.
"""
import os
from dataclasses import dataclass, field


class NotConfigured(Exception):
    """The provider exists only as a plan; nothing is connected."""


@dataclass
class AssistRequest:
    question: str                      # the patient's words (data, length-limited by the server)
    intent: str | None                 # next | todo | instructions | contact | faq | None (free text the server could not map)
    context: dict = field(default_factory=dict)   # grounded context built by the server (see server.assist_context)


class AssistantProvider:
    name = "base"
    connected_model = None             # None = no AI model connected (the UI label depends on this)
    def answer(self, req: AssistRequest) -> dict:
        raise NotImplementedError


class ScriptedProvider(AssistantProvider):
    """ACTIVE demo provider.  Deterministic: it returns the server-built grounded answer for the matched intent, the scripted
    office-FAQ answer, or 'unknown'.  It never generates text of its own and never sees message or document bodies."""
    name = "scripted"
    connected_model = None
    def answer(self, req):
        g = req.context.get("grounded", {})
        if req.intent in g: return dict(g[req.intent])
        if req.intent == "faq" and req.context.get("faq"): return dict(req.context["faq"])
        return {"kind": "unknown", "short": "I can only answer from your portal records, and I don\u2019t have an answer for that. A person can help \u2014 I can help you send a message.",
                "handoff": {"team": None, "draft": req.question}}


class BedrockProvider(AssistantProvider):
    """STUB - NOT CONNECTED.  Raises NotConfigured on every call.  It documents what a real AWS Bedrock link would need:

    * Credentials: an IAM role attached to the server (or server-side credentials from the host's secret store).  NEVER in the browser,
      never in this repository, never in the snapshot.  Least privilege: bedrock:InvokeModel (and ApplyGuardrail) on the one model ARN.
    * Region: one AWS region chosen with the clinic (data residency), e.g. set as PS_BEDROCK_REGION on the server only.
    * Model ID: one approved model ID / inference profile (PS_BEDROCK_MODEL_ID), pinned and version-reviewed.
    * Compliance: a signed AWS BAA; only HIPAA-eligible services and configuration; model-invocation logging decided deliberately
      (off, or to an encrypted, access-controlled, retention-limited destination); no use of prompts for training.
    * Guardrails: an Amazon Bedrock Guardrail (denied topics: diagnosis, imaging interpretation, medication changes, surgical
      suitability; PII handling; prompt-attack filter; grounding/contextual check) - IN ADDITION to the server's own pre/post rules.
    * Logging and retention: what is stored (the server today stores intent/kind/length only, never the question), for how long, who can see it.
    * Prompting: system prompt = the server rules; the grounded context passed as quoted data; messages/documents marked untrusted;
      output must cite fact ids from the context (the server's post-check drops anything uncited).
    * Operations: timeouts, rate limits, cost limits, an off switch, evaluation set (the api_assist_test cases) run before go-live,
      and clinical sign-off (Dr. Yakel) on the scope and wording.
    """
    name = "bedrock"
    connected_model = None
    REQUIRED = ["IAM role or server-side credentials (never in the browser)", "region", "model ID", "signed AWS BAA + HIPAA-eligible configuration",
                "Bedrock Guardrail ID/version", "logging and retention decision", "Tyler's approval (paid service + credentials)"]
    def answer(self, req):
        raise NotConfigured("AWS Bedrock is not connected in this prototype. Needed first: " + "; ".join(self.REQUIRED) + ".")


PROVIDERS = {"scripted": ScriptedProvider, "bedrock": BedrockProvider}

def get_provider(name=None):
    """PS_ASSISTANT_PROVIDER selects the provider (default 'scripted').  Unknown names fall back to 'scripted'."""
    n = (name or os.environ.get("PS_ASSISTANT_PROVIDER") or "scripted").strip().lower()
    return PROVIDERS.get(n, ScriptedProvider)()
