"""Word documents on the JUP templates (O1 1/3, #44): `jup.office_doc`.

Every test renders a real template from `backend/jup/office_templates/` and reads the result
back with python-docx, so what is asserted is what Word will open.
"""

import hashlib
import io
import json
from pathlib import Path

import pytest
from docx import Document
from docx.oxml.ns import nsmap, qn
from lxml import etree

from jup import office_doc
from jup.office_doc import OfficeDocError, classification_for, outline, render, templates

TEMPLATE_DIR = Path(office_doc.__file__).resolve().parent / 'office_templates'

BLOCKS = [
    {'type': 'heading', 'level': 1, 'text': 'Latar belakang'},
    {'type': 'paragraph', 'text': 'SPBG Pemuda kembali beroperasi dengan **dua dispenser**.'},
    {'type': 'bullets', 'items': ['Pasokan gas tersedia', 'Izin masih berlaku']},
    {'type': 'numbered', 'items': ['Uji tekanan', 'Serah terima']},
    {'type': 'table', 'header': ['Lokasi', 'Status'], 'rows': [['Pemuda', 'Aktif'], ['Pulogadung', 'Idle']]},
    {'type': 'note', 'text': 'Angka bersifat indikatif.'},
]


def _doc(rendered) -> Document:
    return Document(io.BytesIO(rendered.data))


def _xp(el, expr: str):
    return etree.XPath(expr, namespaces={'w': nsmap['w']})(el)


def _tag_text(root, tag: str) -> list[str]:
    return [
        ''.join(_xp(s, './/w:sdtContent//w:t/text()'))
        for s in root.iter(qn('w:sdt'))
        if _xp(s, 'string(./w:sdtPr/w:tag/@w:val)') == tag
    ]


def _text(paragraph) -> str:
    """A paragraph's text including its content controls, which `paragraph.text` skips."""
    return ''.join(_xp(paragraph._p, './/w:t/text()'))


def _footer_roots(document):
    return [rel.target_part.element for rel in document.part.rels.values() if rel.reltype.endswith('/footer')]


def _body_styles(document) -> list[str]:
    return [p.style.style_id for p in document.paragraphs]


# -- the template set --------------------------------------------------------------------------


def test_sixteen_templates_are_pinned_and_the_letter_is_left_out():
    manifest = json.loads((TEMPLATE_DIR / 'manifest.json').read_text(encoding='utf-8'))
    assert len(templates()) == 16
    assert 'SRT' not in templates()
    assert '17-JUP-Surat-Resmi.docx' in manifest['excluded']
    on_disk = sorted(p.name for p in (TEMPLATE_DIR / 'docx').glob('*.docx'))
    assert on_disk == sorted(t.file for t in templates().values())
    for t in templates().values():
        assert hashlib.sha256(t.path.read_bytes()).hexdigest() == t.sha256, t.file


@pytest.mark.parametrize('code', sorted(templates()))
def test_every_template_renders_as_a_draft_with_its_group(code):
    rendered = render(code, 'Judul uji', BLOCKS)
    document = _doc(rendered)
    assert _tag_text(document.element.body, 'JUP-STATUS') == ['Draf']
    footers = _footer_roots(document)
    assert [t for f in footers for t in _tag_text(f, 'JUP-ACCESS')] == ['INTERNAL'] * len(
        [t for f in footers for t in _tag_text(f, 'JUP-ACCESS')]
    )
    assert {t for f in footers for t in _tag_text(f, 'JUP-GROUP')} == {templates()[code].group}
    assert _text(document.paragraphs[1]) == 'Judul uji'
    assert rendered.filename == f'JUP-{code}-Judul-uji-Draf.docx'


def test_the_body_is_the_spec_in_the_template_styles():
    document = _doc(render('MEM', 'Reaktivasi SPBG Pemuda', BLOCKS))
    styles = _body_styles(document)
    assert styles[:2] == ['JUPEyebrow', 'Title']
    body = styles[styles.index('Heading1') :]
    assert body[:7] == ['Heading1', 'Normal', 'ListBullet', 'ListBullet', 'ListNumber', 'ListNumber', 'Normal']
    assert 'JUPNote' in body
    texts = [p.text for p in document.paragraphs]
    # The template's example body is gone: none of its prompts survive below the head block.
    assert 'Rumusan keputusan yang diminta' not in texts
    assert not any('[' in t for t in texts[texts.index('Latar belakang') :])
    table = document.tables[-1]
    assert [c.text for c in table.rows[0].cells] == ['Lokasi', 'Status']
    assert [c.text for c in table.rows[2].cells] == ['Pulogadung', 'Idle']


def test_a_table_looks_like_the_templates_own_tables():
    table = _doc(render('MEM', 'Uji', BLOCKS)).tables[-1]
    fills = [_xp(row.cells[0]._tc, 'string(./w:tcPr/w:shd/@w:fill)') for row in table.rows]
    assert fills == ['004999', 'FFFFFF', 'F0F1F1']
    header_run = table.rows[0].cells[0].paragraphs[0].runs[0]
    assert header_run.bold and str(header_run.font.color.rgb) == 'FFFFFF'
    assert str(table.rows[1].cells[0].paragraphs[0].runs[0].font.color.rgb) == '011627'
    assert {c.paragraphs[0].style.style_id for row in table.rows for c in row.cells} == {'JUPTable'}
    assert _xp(table.rows[0]._tr, 'string(./w:trPr/w:tblHeader/@w:val)') == 'true'


def test_bold_markup_becomes_bold_runs():
    document = _doc(render('MEM', 'Uji', BLOCKS))
    paragraph = next(p for p in document.paragraphs if p.text.startswith('SPBG Pemuda'))
    assert paragraph.text == 'SPBG Pemuda kembali beroperasi dengan dua dispenser.'
    assert [r.text for r in paragraph.runs if r.bold] == ['dua dispenser']


def test_header_and_footer_parts_stay_the_templates():
    before = Document(str(templates()['NOT'].path))
    after = _doc(render('NOT', 'Rapat mingguan', BLOCKS))
    assert [p.text for p in after.sections[0].header.paragraphs] == [
        p.text for p in before.sections[0].header.paragraphs
    ]
    assert len(_footer_roots(after)) == len(_footer_roots(before))


# -- metadata ----------------------------------------------------------------------------------


def test_given_metadata_is_filled_and_the_rest_keeps_its_prompt():
    rendered = render('MEM', 'Uji', BLOCKS, metadata={'unit': 'OPS', 'owner': 'Direktorat Operasional'})
    head = [_text(p) for p in _doc(rendered).paragraphs[:6]]
    assert head[2] == 'JUP–MEM–OPS–[NOMOR]  |  Versi [x.y]'
    assert head[3] == 'Pemilik: Direktorat Operasional  |  Tanggal: [Tanggal dokumen]'
    assert head[5] == 'Status: Draf'
    assert rendered.unfilled == ['number', 'version', 'date', 'distribution']


def test_unknown_metadata_is_refused_not_dropped():
    with pytest.raises(OfficeDocError, match='Unknown metadata: status'):
        render('MEM', 'Uji', BLOCKS, metadata={'status': 'Disetujui'})


def test_core_properties_name_the_draft():
    props = _doc(render('SOP', 'Pengisian CNG', BLOCKS, author='Erik')).core_properties
    assert props.title == 'Pengisian CNG'
    assert props.author == 'Erik'
    assert props.last_modified_by == 'Asisten JUP'
    assert 'Draf' in props.comments


# -- classification ----------------------------------------------------------------------------


def test_classification_defaults_to_internal():
    assert classification_for(None) == 'INTERNAL'
    assert classification_for('terbatas') == 'TERBATAS'


def test_publik_is_refused():
    with pytest.raises(OfficeDocError, match='PUBLIK'):
        render('MEM', 'Uji', BLOCKS, classification='PUBLIK')


def test_a_floor_raises_the_classification_and_never_lowers_it():
    assert classification_for('INTERNAL', floor='TERBATAS') == 'TERBATAS'
    assert classification_for('RAHASIA', floor='TERBATAS') == 'RAHASIA'
    rendered = render('MEM', 'Uji', BLOCKS, classification='INTERNAL', floor='RAHASIA')
    assert rendered.classification == 'RAHASIA'
    footers = _footer_roots(_doc(rendered))
    assert {t for f in footers for t in _tag_text(f, 'JUP-ACCESS')} == {'RAHASIA'}


@pytest.mark.parametrize('bad', ['SECRET', 'publik ', 'Rahasia!'])
def test_an_unknown_classification_is_refused(bad):
    with pytest.raises(OfficeDocError):
        classification_for(bad)


# -- refusals ----------------------------------------------------------------------------------


def test_an_unknown_template_lists_the_real_ones():
    with pytest.raises(OfficeDocError, match='MEM \\(Memo usulan keputusan\\)'):
        render('SRT', 'Surat', BLOCKS)


@pytest.mark.parametrize(
    'blocks, message',
    [
        ([], 'no content'),
        ([{'type': 'image'}], 'type "image"'),
        ([{'type': 'heading', 'level': 4, 'text': 'x'}], 'level is 1, 2 or 3'),
        ([{'type': 'paragraph', 'text': '   '}], 'is empty'),
        ([{'type': 'bullets', 'items': []}], 'non-empty list'),
        ([{'type': 'table', 'header': ['a', 'b'], 'rows': [['1']]}], 'exactly 2 cells'),
        ([{'type': 'table', 'header': ['c'] * 13, 'rows': [['x'] * 13]}], 'at most 12 columns'),
        ([{'type': 'paragraph', 'text': 'x' * 4001}], 'limit is 4000'),
        ([{'type': 'paragraph', 'text': 'x'}] * 201, 'limit is 200'),
        ([{'type': 'paragraph', 'text': 'x' * 4000}] * 16, 'limit is 60000'),
    ],
)
def test_limits_are_refused_with_a_reason(blocks, message):
    with pytest.raises(OfficeDocError, match=message):
        render('MEM', 'Uji', blocks)


def test_a_tampered_template_is_refused(monkeypatch, tmp_path):
    tpl = templates()['MEM']
    (tmp_path / 'docx').mkdir()
    (tmp_path / 'docx' / tpl.file).write_bytes(tpl.path.read_bytes() + b'\0')
    monkeypatch.setattr(office_doc, 'TEMPLATE_DIR', tmp_path)
    with pytest.raises(OfficeDocError, match='does not match its pinned copy'):
        render('MEM', 'Uji', BLOCKS)


# -- outline and catalogue ---------------------------------------------------------------------


def test_the_outline_shows_the_templates_structure():
    text = outline('MEM')
    assert text.startswith('# MEM: Memo usulan keputusan')
    assert '### Rumusan keputusan yang diminta' in text
    assert '[table: ' in text


def test_the_catalogue_names_every_template_once():
    lines = office_doc.catalogue().splitlines()
    assert len(lines) == 16
    assert lines[0].startswith('- WHP: Whitepaper perusahaan')


def test_the_module_imports_nothing_from_the_app():
    source = Path(office_doc.__file__).read_text(encoding='utf-8')
    assert 'open_webui' not in source
    assert 'requests' not in source and 'httpx' not in source
