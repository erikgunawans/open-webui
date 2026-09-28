"""#27: `deploy/gcp/sync-voice-model.ts` says what the plan names and what `jup.voice_turn` enforces.

Source reads, so it runs under `--only-group dev`. The script itself runs in Erik's tab; its
`--dry-run` is the live check.
"""

import re
from pathlib import Path

from jup import voice, voice_turn

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / 'deploy' / 'gcp' / 'sync-voice-model.ts').read_text(encoding='utf-8')
PLAN = (ROOT / '.planning' / 'agent-depth-plan.md').read_text(encoding='utf-8')
VENDOR_TOOLS = (ROOT / 'backend' / 'open_webui' / 'utils' / 'tools.py').read_text(encoding='utf-8')


def _script_documents() -> list[str]:
    block = SCRIPT[SCRIPT.index('const VOICE_DOCUMENTS') : SCRIPT.index('];', SCRIPT.index('const VOICE_DOCUMENTS'))]
    return [f'{path}/{name}' for path, name in re.findall(r'path: "([^"]+)", filename: "([^"]+)"', block)]


def _plan_documents() -> list[str]:
    at = PLAN.index('**Named voice document set')
    block = PLAN[at : PLAN.index('Out:', at)]
    return [f'{name}.md' for name in re.findall(r'`([a-z0-9/-]+)`', block)]


def test_the_script_names_exactly_the_plans_eight_documents():
    assert len(_plan_documents()) == 8
    assert sorted(_script_documents()) == sorted(_plan_documents())


def test_none_of_the_documents_the_plan_leaves_out_is_named():
    assert not any('partners' in d or 'DECISIONS' in d or 'engagements' in d for d in _script_documents())


def test_the_model_id_and_tools_match_what_the_code_enforces():
    assert f'const VOICE_MODEL_ID = "{voice.VOICE_MODEL_ID}"' in SCRIPT
    tools = re.search(r'const VOICE_TOOL_IDS = \[([^\]]*)\]', SCRIPT).group(1)
    assert re.findall(r'"([^"]+)"', tools) == list(voice_turn.VOICE_TOOL_IDS)


def test_every_vendor_builtin_category_is_switched_by_the_script():
    """A category the vendor adds defaults to on; the script must name it to turn it off."""
    vendor = set(re.findall(r"is_builtin_tool_enabled\('([a-z_]+)'", VENDOR_TOOLS))
    block = SCRIPT[
        SCRIPT.index('const BUILTIN_CATEGORIES') : SCRIPT.index('];', SCRIPT.index('const BUILTIN_CATEGORIES'))
    ]
    assert set(re.findall(r'"([a-z_]+)"', block)) == vendor


def test_only_the_knowledge_category_stays_on():
    assert "Object.fromEntries(P.categories.map((c) => [c, c === 'knowledge']))" in SCRIPT


def test_a_dry_run_writes_nothing():
    """Every write sits after the `P.check` return."""
    program = SCRIPT[SCRIPT.index('const PROGRAM = `') :]
    stop = program.index("if (P.check || action === 'unmodified') return out;")
    assert "method: 'POST', headers: json, body: JSON.stringify({ manifest })" in program[:stop]  # sync/diff only
    assert '/api/v1/models/create' not in program[:stop]
    assert '/api/v1/models/model/update' not in program[:stop]


def test_a_missing_document_refuses_before_any_write():
    program = SCRIPT[SCRIPT.index('const PROGRAM = `') :]
    assert program.index("return { refused: 'named voice documents missing from the KB', missing }") < program.index(
        '/api/v1/models/create'
    )
    assert 'process.exit(1)' in SCRIPT[: SCRIPT.index('const PROGRAM')]  # the local check


def test_a_new_model_is_admin_only_and_an_update_keeps_its_grants():
    assert 'JSON.stringify({ ...form, access_grants: [] })' in SCRIPT
    update = SCRIPT[SCRIPT.index("'/api/v1/models/model/update'") :]
    assert 'access_grants' not in update[: update.index('\n')]


def test_the_voice_instructions_answer_the_call_uis_exact_opening_line():
    """The greeting and pantun are keyed on one line; the UI and the model must agree on it."""
    call_ts = (ROOT / 'src' / 'lib' / 'voice' / 'call.ts').read_text(encoding='utf-8')
    ui = re.search(r"export const CALL_OPENING = '([^']+)';", call_ts).group(1)
    script = re.search(r'const CALL_OPENING = "([^"]+)";', SCRIPT).group(1)
    assert ui == script


def test_the_voice_instructions_greet_by_name_with_a_betawi_pantun_and_are_sent():
    block = SCRIPT[
        SCRIPT.index('const VOICE_INSTRUCTIONS') : SCRIPT.index('].join(', SCRIPT.index('const VOICE_INSTRUCTIONS'))
    ]
    assert '{{USER_NAME}}' in block
    assert 'pantun Betawi' in block
    assert 'jangan memanggil tool' in block
    assert 'voiceInstructions: VOICE_INSTRUCTIONS' in SCRIPT
    # Appended to Asisten JUP's own system prompt, never replacing it.
    assert '[(base.params || {}).system, P.voiceInstructions].filter(Boolean)' in SCRIPT


def test_every_voice_turn_answers_in_indonesian_and_asks_again_when_unclear():
    """The first live calls heard Japanese and Chinese in noise and answered in those languages."""
    block = SCRIPT[
        SCRIPT.index('const VOICE_INSTRUCTIONS') : SCRIPT.index('].join(', SCRIPT.index('const VOICE_INSTRUCTIONS'))
    ]
    assert 'Selalu jawab dalam Bahasa Indonesia' in block
    assert 'minta pengguna mengulang' in block
    assert 'tanpa daftar' in block


def test_the_description_is_written_for_staff_not_maintainers():
    """The model description shows on the voice chat's home screen. It said "Generated by
    deploy/gcp/sync-voice-model.ts … edit the script" and cited an ADR, in English, to staff."""
    desc = re.search(r'const DESCRIPTION =\s*((?:"[^"]*"\s*\+?\s*)+);', SCRIPT).group(1)
    for leak in ('Generated by', 'sync-voice-model', 'ADR', 'edit the script'):
        assert leak not in desc
    assert 'panggilan suara' in desc.lower()
