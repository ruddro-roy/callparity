"""Property-based fuzz of the phone-redaction safety net.

The redactor is the last line of defense before stdout, so example-based
tests are not enough: these properties hold for every input hypothesis can
construct, not just the samples a developer thought of. All phone-shaped
material is generated at runtime; no phone-shaped literal lives in this file.

Pinned invariants: no E.164-shaped run ever survives redaction, however the
run is embedded or nested; container shape, keys, and non-string scalars are
preserved; redaction is idempotent; strings without a plus sign pass through
untouched; and mask_e164 always hides the middle of anything phone-shaped.
Runs are derandomized so CI is deterministic.
"""

from app.logging_conf import _LOG_PHONE, _redact_phones_processor, mask_e164, redact_log_value
from hypothesis import given, settings
from hypothesis import strategies as st

DIGITS = "0123456789"
# The characters _LOG_PHONE accepts inside a run, after the leading +digit.
RUN_BODY = DIGITS + " ().-"

DETERMINISTIC = settings(derandomize=True, deadline=None, max_examples=200)

phone_runs = st.builds(
    lambda first, body, last: f"+{first}{body}{last}",
    st.sampled_from(DIGITS),
    st.text(alphabet=RUN_BODY, min_size=6, max_size=18),
    st.sampled_from(DIGITS),
)

benign_text = st.text(max_size=40)

texts_with_embedded_phone = st.builds(
    lambda prefix, run, suffix: prefix + run + suffix,
    benign_text,
    phone_runs,
    benign_text,
)

any_text = st.one_of(benign_text, texts_with_embedded_phone, phone_runs)

scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False),
    any_text,
)

structures = st.recursive(
    scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(max_size=8), children, max_size=4),
        st.tuples(children, children),
    ),
    max_leaves=12,
)


def no_phone_anywhere(value) -> bool:
    if isinstance(value, str):
        return _LOG_PHONE.search(value) is None
    if isinstance(value, dict):
        return all(no_phone_anywhere(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(no_phone_anywhere(v) for v in value)
    return True


def same_shape(original, redacted) -> bool:
    if isinstance(original, dict):
        return (
            isinstance(redacted, dict)
            and original.keys() == redacted.keys()
            and all(same_shape(original[k], redacted[k]) for k in original)
        )
    if isinstance(original, (list, tuple)):
        return (
            type(original) is type(redacted)
            and len(original) == len(redacted)
            and all(same_shape(a, b) for a, b in zip(original, redacted))
        )
    if isinstance(original, str):
        return isinstance(redacted, str)
    return original == redacted


@DETERMINISTIC
@given(phone_runs)
def test_generated_runs_really_are_phone_shaped(run):
    """Sanity for the generator itself: every run would trip the regex raw."""
    assert _LOG_PHONE.search(run) is not None


@DETERMINISTIC
@given(texts_with_embedded_phone)
def test_no_embedded_run_survives_redaction(text):
    redacted = redact_log_value(text)
    assert _LOG_PHONE.search(redacted) is None
    assert "[phone]" in redacted


@DETERMINISTIC
@given(structures)
def test_no_run_survives_at_any_nesting_depth(value):
    redacted = redact_log_value(value)
    assert no_phone_anywhere(redacted)
    assert same_shape(value, redacted)


@DETERMINISTIC
@given(structures)
def test_redaction_is_idempotent(value):
    once = redact_log_value(value)
    assert redact_log_value(once) == once


@DETERMINISTIC
@given(benign_text.filter(lambda s: "+" not in s))
def test_text_without_plus_passes_through_untouched(text):
    assert redact_log_value(text) == text


@DETERMINISTIC
@given(phone_runs)
def test_mask_e164_hides_the_middle_of_every_run(run):
    masked = mask_e164(run)
    assert "***" in masked
    assert run[1:] not in masked  # the full digit body never survives


@DETERMINISTIC
@given(st.dictionaries(st.text(min_size=1, max_size=8), any_text, max_size=5))
def test_processor_scrubs_every_event_field(event):
    scrubbed = _redact_phones_processor(None, "info", dict(event))
    assert set(scrubbed) == set(event)
    assert no_phone_anywhere(scrubbed)
