"""What the web app shows around a Link Code (E9.2, #103): the WhatsApp number to send it to and the Meta notice.

Pure, so it is tested without the vendor runtime. The route in `routers/jup_whatsapp_link.py` is the shell.
"""

import os
from collections.abc import Mapping
from urllib.parse import quote

#: The business number the gateway answers on, digits only. Unset: Meta's test number for the Axiara
#: developer app (E9 builds on it; JUP's own number comes with go-live).
NUMBER_ENV = 'JUP_WHATSAPP_NUMBER'
TEST_NUMBER = '15556537220'

#: Shown before a user links (spec #101). Erik's to change.
DISCLOSURE = 'Pesan WhatsApp melewati server Meta (termasuk di Amerika Serikat) sebelum sampai ke Asisten JUP.'


def whatsapp_number(env: Mapping[str, str] | None = None) -> str:
    """The configured number with everything but digits removed, or the test number."""
    source = os.environ if env is None else env
    digits = ''.join(ch for ch in (source.get(NUMBER_ENV) or '') if ch.isascii() and ch.isdigit())
    return digits or TEST_NUMBER


def wa_link(number: str, code: str) -> str:
    """Opens WhatsApp with `hubungkan <code>` typed, addressed to `number`."""
    return f'https://wa.me/{number}?text={quote(f"hubungkan {code}")}'
