"""What the web app shows around a Link Code (`jup.channel_links.web`, E9.2, #103).

Pure: runs under `--only-group dev`.
"""

from jup.channel_links import web


def test_the_number_defaults_to_the_test_number_and_keeps_digits_only():
    assert web.whatsapp_number({}) == web.TEST_NUMBER
    assert web.whatsapp_number({web.NUMBER_ENV: '   '}) == web.TEST_NUMBER
    assert web.whatsapp_number({web.NUMBER_ENV: '+62 812-3456-7890'}) == '6281234567890'


def test_the_wa_link_opens_whatsapp_with_the_command_typed():
    assert web.wa_link('15556537220', '048213') == 'https://wa.me/15556537220?text=hubungkan%20048213'


def test_the_disclosure_names_meta_and_the_united_states():
    assert 'Meta' in web.DISCLOSURE
    assert 'Amerika Serikat' in web.DISCLOSURE
