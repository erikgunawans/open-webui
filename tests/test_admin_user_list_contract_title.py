"""The contract title column in Admin → Pengguna (D3).

`UserList.svelte` is vendor code. A rebase (ADR-0007) that takes upstream's side of a conflict drops
the column silently: the API still works, and no admin can set anyone's title. A source read catches
it under `--only-group dev`. See `deploy/gcp/VENDOR-PATCHES.md`.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_LIST = ROOT / 'src' / 'lib' / 'components' / 'admin' / 'Users' / 'UserList.svelte'
SELECT = ROOT / 'src' / 'lib' / 'components' / 'contracts' / 'ContractTitleSelect.svelte'


def test_the_user_list_imports_the_select() -> None:
    source = USER_LIST.read_text(encoding='utf-8')
    assert "import ContractTitleSelect from '$lib/components/contracts/ContractTitleSelect.svelte';" in source


def test_the_column_has_a_header_and_a_cell() -> None:
    source = USER_LIST.read_text(encoding='utf-8')
    # Prettier decides where the tag breaks, so whitespace around the label is free.
    assert re.search(r"<th scope=\"col\"[^>]*>\s*\{\$i18n\.t\('Title group'\)\}\s*</th\s*>", source)
    assert '<ContractTitleSelect userId={user.id} userName={user.name} />' in source
    # One column: one header and one cell.
    assert source.count('<ContractTitleSelect') == 1


def test_the_select_calls_the_contracts_api() -> None:
    source = SELECT.read_text(encoding='utf-8')
    assert 'getContractTitles' in source and 'setContractTitle' in source


CONTENT_RENDERER = ROOT / 'src' / 'lib' / 'components' / 'chat' / 'Messages' / 'ContentRenderer.svelte'


def test_answers_pass_through_the_contract_names_store() -> None:
    """D2: Legal and Direksi see names beside "Perorangan X". Both render paths use formatMessageContent."""
    source = CONTENT_RENDERER.read_text(encoding='utf-8')
    assert "import { contractNames, loadContractNames, withContractNames } from '$lib/stores/contractNames';" in source
    assert '$: loadContractNames($user?.id);' in source
    assert re.search(
        r'\$: formatMessageContent = \(messageContent\) =>\s*withContractNames\(\s*\$contractNames,', source
    )
    assert source.count('formatMessageContent(content)') == 1 and '{formatMessageContent}' in source
